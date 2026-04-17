"""Tests for analysis-depth handling in task_generator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.github_parser import GitHubRepo
from src.youtube_parser import YouTubeVideo
from src.task_generator import (
    STANDARD_DEPTH,
    DETAILED_DEPTH,
    _resolve_depth_config,
    _resolve_video_depth_config,
    create_repo_analysis_task,
    create_video_summary_task,
)


def _make_repo() -> GitHubRepo:
    return GitHubRepo(
        owner="acme",
        repo="widgets",
        url="https://github.com/acme/widgets",
    )


def _make_video() -> YouTubeVideo:
    return YouTubeVideo(video_id="abc12345678", url="https://youtu.be/abc12345678")


def test_repo_depth_config_standard():
    cfg = _resolve_depth_config(STANDARD_DEPTH)
    assert cfg["agent"] == "repo-analyzer"
    assert cfg["complexity_score"] == "50"
    assert cfg["priority_bump"] is None


def test_repo_depth_config_detailed():
    cfg = _resolve_depth_config(DETAILED_DEPTH)
    assert cfg["agent"] == "repo-analyzer-detailed"
    assert cfg["complexity_score"] == "85"
    assert cfg["priority_bump"] == "High"


def test_repo_depth_config_unknown_falls_back_to_standard():
    cfg = _resolve_depth_config("bogus")
    assert cfg["agent"] == "repo-analyzer"


def test_video_depth_config_standard():
    cfg = _resolve_video_depth_config(STANDARD_DEPTH)
    assert cfg["agent"] == "video-summarizer"
    assert cfg["complexity_score"] == "40"


def test_video_depth_config_detailed():
    cfg = _resolve_video_depth_config(DETAILED_DEPTH)
    assert cfg["agent"] == "video-summarizer-detailed"
    assert cfg["complexity_score"] == "75"
    assert cfg["priority_bump"] == "High"


def test_create_repo_task_standard_includes_repo_analyzer():
    repo = _make_repo()
    task = create_repo_analysis_task(
        repo=repo,
        clone_dir=Path("/tmp/clone"),
        analysis_dir=Path("/tmp/analysis"),
        user_prompt="do a standard review",
        analysis_depth=STANDARD_DEPTH,
    )
    assert "**Analysis-Depth:** standard" in task
    assert "**Target Agent:** repo-analyzer" in task
    assert "**Complexity-Score:** 50" in task
    assert '"agent": "repo-analyzer"' in task
    assert '"analysis_depth": "standard"' in task


def test_create_repo_task_detailed_uses_detailed_variant():
    repo = _make_repo()
    task = create_repo_analysis_task(
        repo=repo,
        clone_dir=Path("/tmp/clone"),
        analysis_dir=Path("/tmp/analysis"),
        user_prompt="go deep",
        analysis_depth=DETAILED_DEPTH,
    )
    assert "**Analysis-Depth:** detailed" in task
    assert "**Target Agent:** repo-analyzer-detailed" in task
    assert "**Priority:** High" in task
    assert "**Complexity-Score:** 85" in task
    assert '"agent": "repo-analyzer-detailed"' in task
    assert '"analysis_depth": "detailed"' in task


def test_create_video_task_standard():
    video = _make_video()
    task = create_video_summary_task(
        video=video,
        transcript_dir=Path("/tmp/transcripts"),
        analysis_depth=STANDARD_DEPTH,
    )
    assert "**Analysis-Depth:** standard" in task
    assert "**Target Agent:** video-summarizer" in task
    assert '"agent": "video-summarizer"' in task


def test_create_video_task_detailed():
    video = _make_video()
    task = create_video_summary_task(
        video=video,
        transcript_dir=Path("/tmp/transcripts"),
        analysis_depth=DETAILED_DEPTH,
    )
    assert "**Analysis-Depth:** detailed" in task
    assert "**Target Agent:** video-summarizer-detailed" in task
    assert "**Priority:** High" in task
    assert "**Complexity-Score:** 75" in task
    assert '"agent": "video-summarizer-detailed"' in task
    assert '"analysis_depth": "detailed"' in task


def test_detailed_repo_task_priority_overrides_caller_default():
    """Detailed mode bumps priority even if caller passed Medium."""
    repo = _make_repo()
    task = create_repo_analysis_task(
        repo=repo,
        clone_dir=Path("/tmp/clone"),
        analysis_dir=Path("/tmp/analysis"),
        priority="Low",
        analysis_depth=DETAILED_DEPTH,
    )
    assert "**Priority:** High" in task
    assert "**Priority:** Low" not in task


if __name__ == "__main__":
    tests = [
        test_repo_depth_config_standard,
        test_repo_depth_config_detailed,
        test_repo_depth_config_unknown_falls_back_to_standard,
        test_video_depth_config_standard,
        test_video_depth_config_detailed,
        test_create_repo_task_standard_includes_repo_analyzer,
        test_create_repo_task_detailed_uses_detailed_variant,
        test_create_video_task_standard,
        test_create_video_task_detailed,
        test_detailed_repo_task_priority_overrides_caller_default,
    ]
    for t in tests:
        t()
        print(f"ok - {t.__name__}")
    print("All tests passed!")
