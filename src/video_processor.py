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

DETAILED_VIDEO_PROMPT = (
    "Produce an IN-DEPTH breakdown of this video transcript. Go beyond a surface "
    "summary — extract everything a viewer would want to reference later.\n\n"
    "1. One-paragraph plain-language description.\n"
    "2. Speaker/presenter perspective, credentials, and biases worth noting.\n"
    "3. Section-by-section breakdown with rough positional markers.\n"
    "4. Every key point and main takeaway, with supporting context.\n"
    "5. Every technical concept, tool, library, or framework mentioned — each with "
    "a one-line explanation.\n"
    "6. Code snippets, commands, and config values shown — reproduced verbatim.\n"
    "7. Claims vs evidence — flag anything unsupported.\n"
    "8. Counterarguments, caveats, and exceptions the speaker notes.\n"
    "9. Actionable checklist of steps/advice.\n"
    "10. External resources referenced (links, books, papers, repos, tools).\n"
    "11. Who this is useful for — and who should skip.\n"
    "12. Opinionated verdict: is this worth the viewer's time?\n\n"
    "Preserve technical accuracy over brevity. Quote the speaker when phrasing matters."
)

CLAUDE_PATH = os.environ.get("CLAUDE_PATH", "/home/shaddar/.nvm/versions/node/v20.10.0/bin/claude")
#Detailed analyses go through a stronger model; standard keeps the default.
DETAILED_MODEL = os.environ.get("CLAUDE_DETAILED_MODEL", "opus")
STANDARD_DEPTH = "standard"
DETAILED_DEPTH = "detailed"


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


def _prompt_for(depth: str) -> str:
    """Pick the prompt that matches the requested analysis depth."""
    return DETAILED_VIDEO_PROMPT if depth == DETAILED_DEPTH else VIDEO_PROMPT


def _transcript_budget(depth: str) -> int:
    """Detailed mode reads more of the transcript before hitting the cap."""
    return 180_000 if depth == DETAILED_DEPTH else 100_000


def summarize_with_claude(
    transcript: str,
    video_title: str | None = None,
    depth: str = STANDARD_DEPTH,
) -> str:
    """Send transcript to local Claude CLI. Detailed mode uses a longer prompt + larger model."""
    prompt = _prompt_for(depth) + "\n\n"
    if video_title:
        prompt += f"Video title: {video_title}\n\n"
    prompt += f"Transcript:\n{transcript[:_transcript_budget(depth)]}"

    cmd = [CLAUDE_PATH, "-p"]
    if depth == DETAILED_DEPTH and DETAILED_MODEL:
        cmd.extend(["--model", DETAILED_MODEL])
    #Detailed analyses are longer — bump the subprocess timeout accordingly.
    timeout = 600 if depth == DETAILED_DEPTH else 300

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True, text=True, timeout=timeout,
    )

    if result.returncode != 0:
        log.error("claude_failed", exit_code=result.returncode, depth=depth, stderr=result.stderr[:500])
        raise RuntimeError(
            f"Claude CLI failed (exit {result.returncode}): {result.stderr.strip()[:300]}"
        )

    return result.stdout.strip()


async def process_video(
    url: str,
    video_id: str,
    transcript_dir: Path,
    depth: str = STANDARD_DEPTH,
) -> tuple[str, str | None]:
    """
    Full pipeline: transcribe -> summarize -> save.

    Returns (summary_text, video_title)
    """
    import asyncio

    loop = asyncio.get_event_loop()

    log.info("fetching_video_info", video_id=video_id, depth=depth)
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

    log.info("summarizing", video_id=video_id, depth=depth)
    summary = await loop.run_in_executor(
        None, summarize_with_claude, transcript, video_title, depth,
    )

    return summary, video_title
