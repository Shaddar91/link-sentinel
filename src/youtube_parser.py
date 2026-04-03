"""YouTube URL parsing and validation."""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class YouTubeVideo:
    """Parsed YouTube video information."""
    video_id: str
    url: str

    @property
    def full_name(self) -> str:
        """Return display name."""
        return f"youtube/{self.video_id}"

    @property
    def folder_name(self) -> str:
        """Return folder name for local storage."""
        return f"yt_{self.video_id}"


# Regex patterns for YouTube URLs
# Each uses a negative lookahead to ensure the 11-char video ID isn't part of a longer string
_ID = r'([a-zA-Z0-9_-]{11})(?![a-zA-Z0-9_-])'

YOUTUBE_PATTERNS = [
    # https://www.youtube.com/watch?v=VIDEO_ID (with optional params)
    re.compile(rf'https?://(?:www\.|m\.)?youtube\.com/watch\?[^\s]*v={_ID}'),
    # https://youtu.be/VIDEO_ID
    re.compile(rf'https?://youtu\.be/{_ID}'),
    # https://www.youtube.com/shorts/VIDEO_ID
    re.compile(rf'https?://(?:www\.|m\.)?youtube\.com/shorts/{_ID}'),
    # https://www.youtube.com/live/VIDEO_ID
    re.compile(rf'https?://(?:www\.|m\.)?youtube\.com/live/{_ID}'),
    # https://www.youtube.com/embed/VIDEO_ID
    re.compile(rf'https?://(?:www\.|m\.)?youtube\.com/embed/{_ID}'),
    # https://www.youtube.com/v/VIDEO_ID (old embed)
    re.compile(rf'https?://(?:www\.|m\.)?youtube\.com/v/{_ID}'),
]


def extract_youtube_urls(text: str) -> list[YouTubeVideo]:
    """
    Extract all YouTube video URLs from text.

    Args:
        text: Text that may contain YouTube URLs

    Returns:
        List of parsed YouTubeVideo objects
    """
    videos = []
    seen = set()

    for pattern in YOUTUBE_PATTERNS:
        for match in pattern.finditer(text):
            video_id = match.group(1)

            if video_id not in seen:
                seen.add(video_id)
                videos.append(YouTubeVideo(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                ))

    return videos


def parse_youtube_url(url: str) -> Optional[YouTubeVideo]:
    """
    Parse a single YouTube URL.

    Args:
        url: YouTube URL to parse

    Returns:
        YouTubeVideo if valid, None otherwise
    """
    videos = extract_youtube_urls(url)
    return videos[0] if videos else None


def is_youtube_url(text: str) -> bool:
    """
    Check if text contains a YouTube video URL.

    Args:
        text: Text to check

    Returns:
        True if contains YouTube URL
    """
    return bool(extract_youtube_urls(text))
