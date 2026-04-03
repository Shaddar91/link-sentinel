"""Tests for YouTube URL parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.youtube_parser import (
    extract_youtube_urls,
    parse_youtube_url,
    is_youtube_url,
    YouTubeVideo,
)


def test_parse_standard_url():
    """Test parsing standard YouTube watch URL."""
    video = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"
    assert video.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_parse_short_url():
    """Test parsing youtu.be short URL."""
    video = parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_shorts_url():
    """Test parsing YouTube Shorts URL."""
    video = parse_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_live_url():
    """Test parsing YouTube live URL."""
    video = parse_youtube_url("https://www.youtube.com/live/dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_embed_url():
    """Test parsing YouTube embed URL."""
    video = parse_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_mobile_url():
    """Test parsing mobile YouTube URL."""
    video = parse_youtube_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_url_without_www():
    """Test parsing URL without www prefix."""
    video = parse_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_parse_url_with_extra_params():
    """Test parsing URL with timestamp and other params."""
    video = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLtest")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_extract_multiple_urls():
    """Test extracting multiple YouTube URLs from text."""
    text = """
    Check this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
    And this one: https://youtu.be/jNQXAC9IVRw
    """
    videos = extract_youtube_urls(text)
    assert len(videos) == 2
    assert videos[0].video_id == "dQw4w9WgXcQ"
    assert videos[1].video_id == "jNQXAC9IVRw"


def test_deduplicate_same_video():
    """Test that same video from different URL formats is deduplicated."""
    text = """
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://youtu.be/dQw4w9WgXcQ
    """
    videos = extract_youtube_urls(text)
    assert len(videos) == 1


def test_is_youtube_url_true():
    """Test is_youtube_url returns True for valid URL."""
    assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_is_youtube_url_false():
    """Test is_youtube_url returns False for non-YouTube URL."""
    assert not is_youtube_url("https://vimeo.com/123456")


def test_folder_name():
    """Test folder name generation."""
    video = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video.folder_name == "yt_dQw4w9WgXcQ"


def test_full_name():
    """Test full name generation."""
    video = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video.full_name == "youtube/dQw4w9WgXcQ"


def test_mixed_github_and_youtube():
    """Test that YouTube parser ignores GitHub URLs."""
    text = "https://github.com/owner/repo and https://youtu.be/dQw4w9WgXcQ"
    videos = extract_youtube_urls(text)
    assert len(videos) == 1
    assert videos[0].video_id == "dQw4w9WgXcQ"


def test_invalid_video_id_length():
    """Test that short/long IDs are not matched."""
    assert not is_youtube_url("https://www.youtube.com/watch?v=short")
    assert not is_youtube_url("https://www.youtube.com/watch?v=waytoolongvideoid123")


if __name__ == "__main__":
    test_parse_standard_url()
    test_parse_short_url()
    test_parse_shorts_url()
    test_parse_live_url()
    test_parse_embed_url()
    test_parse_mobile_url()
    test_parse_url_without_www()
    test_parse_url_with_extra_params()
    test_extract_multiple_urls()
    test_deduplicate_same_video()
    test_is_youtube_url_true()
    test_is_youtube_url_false()
    test_folder_name()
    test_full_name()
    test_mixed_github_and_youtube()
    test_invalid_video_id_length()
    print("All tests passed!")
