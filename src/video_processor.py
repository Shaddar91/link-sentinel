"""Transcribe YouTube videos and summarize with local Claude."""
import subprocess
import json
import os
import re
from pathlib import Path

import structlog

log = structlog.get_logger()

VIDEO_PROMPT = (
    "Summarize this video transcript. Cover the following:\n\n"
    "1. What is the video about? (one paragraph)\n"
    "2. Key points and main takeaways (bullet points)\n"
    "3. Technical details or explanations worth noting\n"
    "4. Actionable steps or practical advice mentioned\n"
    "5. Who is this useful for?\n\n"
    "Be concise and structured. No filler."
)

CLAUDE_PATH = os.environ.get("CLAUDE_PATH", "/home/shaddar/.nvm/versions/node/v20.10.0/bin/claude")


def get_video_info(url: str) -> str | None:
    """Get video title using yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", "--quiet", "--no-warnings", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return info.get("title")
    except Exception as e:
        log.warning("video_info_failed", error=str(e))
    return None


def get_transcript(url: str, video_id: str) -> str | None:
    """Get transcript — try youtube-transcript-api first, fall back to yt-dlp."""
    transcript = _transcript_via_api(video_id)
    if transcript and len(transcript) > 50:
        return transcript

    transcript = _transcript_via_ytdlp(url, video_id)
    if transcript and len(transcript) > 50:
        return transcript

    return None


def _transcript_via_api(video_id: str) -> str | None:
    """Get transcript using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
        except Exception:
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            except Exception:
                return None

        return " ".join([item["text"] for item in transcript_list])
    except ImportError:
        return None
    except Exception as e:
        log.warning("transcript_api_failed", error=str(e))
        return None


def _transcript_via_ytdlp(url: str, video_id: str) -> str | None:
    """Get transcript using yt-dlp subtitle download."""
    try:
        subtitle_attempts = [
            ["--write-auto-subs", "--sub-lang", "en"],
            ["--write-subs", "--sub-lang", "en"],
            ["--write-auto-subs", "--sub-lang", "en-US"],
            ["--write-auto-subs"],
        ]

        for opts in subtitle_attempts:
            subprocess.run(
                ["yt-dlp", *opts, "--skip-download", "--quiet", "--no-warnings",
                 "--sub-format", "vtt/srt/best", "-o", f"/tmp/{video_id}.%(ext)s", url],
                capture_output=True, timeout=60,
            )

            for ext in [".vtt", ".srt"]:
                for lang in ["en", "en-US", "a.en", ""]:
                    fname = f"/tmp/{video_id}.{lang}{ext}" if lang else f"/tmp/{video_id}{ext}"
                    if os.path.exists(fname):
                        with open(fname, "r") as f:
                            content = f.read()
                        os.remove(fname)
                        if content and len(content) > 100:
                            return _clean_vtt(content)
    except Exception as e:
        log.warning("ytdlp_transcript_failed", error=str(e))
    return None


def _clean_vtt(content: str) -> str:
    """Clean VTT/SRT subtitle content to plain text."""
    lines = content.split("\n")
    text_parts = []
    last_text = ""

    for line in lines:
        if ("-->" in line or line.strip().isdigit() or line.strip() == "" or
                line.startswith("WEBVTT") or line.startswith("Kind:") or
                line.startswith("Language:")):
            continue

        clean_line = re.sub(r"<[^>]+>", "", line)
        clean_line = re.sub(r"\{[^}]+\}", "", clean_line)
        clean_line = re.sub(r"\[[^\]]+\]", "", clean_line)
        clean_line = clean_line.strip()

        if clean_line and clean_line != last_text and len(clean_line) > 1:
            text_parts.append(clean_line)
            last_text = clean_line

    return " ".join(text_parts)


def summarize_with_claude(transcript: str, video_title: str | None = None) -> str:
    """Send transcript to local Claude CLI for summarization via stdin pipe."""
    prompt = VIDEO_PROMPT + "\n\n"
    if video_title:
        prompt += f"Video title: {video_title}\n\n"
    prompt += f"Transcript:\n{transcript[:100000]}"

    result = subprocess.run(
        [CLAUDE_PATH, "-p"],
        input=prompt,
        capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0:
        log.error("claude_failed", exit_code=result.returncode, stderr=result.stderr[:500])
        return f"Claude summarization failed (exit {result.returncode})"

    return result.stdout.strip()


async def process_video(url: str, video_id: str, transcript_dir: Path) -> tuple[str, str | None]:
    """
    Full pipeline: transcribe -> summarize -> save.

    Returns (summary_text, video_title)
    """
    import asyncio

    loop = asyncio.get_event_loop()

    log.info("fetching_video_info", video_id=video_id)
    video_title = await loop.run_in_executor(None, get_video_info, url)

    log.info("fetching_transcript", video_id=video_id)
    transcript = await loop.run_in_executor(None, get_transcript, url, video_id)

    if not transcript:
        return "Failed to get transcript. Video may not have captions.", video_title

    # Save raw transcript
    transcript_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[<>:"/\\|?*]', '', video_title or video_id).replace(' ', '_')[:200]
    transcript_path = transcript_dir / f"{safe_title}.txt"
    transcript_path.write_text(
        f"Video Title: {video_title or 'Unknown'}\n"
        f"YouTube URL: {url}\n"
        f"{'='*60}\n\n"
        f"{transcript}"
    )
    log.info("transcript_saved", path=str(transcript_path))

    log.info("summarizing", video_id=video_id)
    summary = await loop.run_in_executor(
        None, summarize_with_claude, transcript, video_title,
    )

    return summary, video_title
