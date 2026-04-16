"""Generate task files for AI Task Automation pipeline."""
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .github_parser import GitHubRepo
from .youtube_parser import YouTubeVideo


def generate_task_id() -> str:
    """Generate unique task ID."""
    now = datetime.now()
    return f"task_{now.strftime('%Y%m%d%H%M%S')}_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:5]}"


def generate_content_hash(content: str) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


DETAILED_DEPTH = "detailed"
STANDARD_DEPTH = "standard"


def _resolve_depth_config(analysis_depth: str) -> dict[str, str]:
    """Pick agent + priority + complexity based on requested analysis depth.

    Detailed mode routes to a stronger analytical agent with a high complexity
    score so the pipeline's orchestrator picks a larger model (Opus).
    """
    if analysis_depth == DETAILED_DEPTH:
        return {
            "depth": DETAILED_DEPTH,
            "agent": "code-reviewer",
            "priority_bump": "High",
            "complexity_score": "85",
            "focus_hint": "deep (architecture, code quality, security, dependencies, competitive landscape)",
        }
    return {
        "depth": STANDARD_DEPTH,
        "agent": "repo-analyzer",
        "priority_bump": None,
        "complexity_score": "50",
        "focus_hint": "standard",
    }


def create_repo_analysis_task(
    repo: GitHubRepo,
    clone_dir: Path,
    analysis_dir: Path,
    analysis_focus: str = "all",
    priority: str = "Medium",
    sender_name: Optional[str] = None,
    user_prompt: str = "",
    analysis_depth: str = STANDARD_DEPTH,
) -> str:
    """
    Create a task file content for repository analysis.

    Args:
        repo: Parsed GitHub repository
        clone_dir: Directory where repo will be cloned
        analysis_dir: Directory where analysis doc will be saved
        analysis_focus: Focus area (architecture, code-quality, features, all)
        priority: Task priority (High, Medium, Low)
        sender_name: Telegram username who sent the link
        user_prompt: The prompt to send to the downstream agent
        analysis_depth: "standard" or "detailed" — picks agent + complexity

    Returns:
        Task file content as string
    """
    task_id = generate_task_id()
    now = datetime.now()
    depth_cfg = _resolve_depth_config(analysis_depth)
    effective_priority = depth_cfg["priority_bump"] or priority
    agent = depth_cfg["agent"]

    summary = f"Analyze GitHub repository {repo.full_name} ({depth_cfg['depth']})"

    context_lines = [
        f"- Repository URL: {repo.url}",
        f"- Source: Telegram link monitor (link-sentinel)",
    ]
    if sender_name:
        context_lines.append(f"- Sent by: {sender_name}")

    clone_path = clone_dir / repo.folder_name
    analysis_path = analysis_dir / f"{repo.folder_name}_analysis.md"

    action_items = [
        f"- [ ] Clone repository to {clone_path}/",
        f"- [ ] Analyze repository architecture and code structure",
        f"- [ ] Document technology stack and dependencies",
        f"- [ ] Assess code quality and patterns",
        f"- [ ] Generate analysis document at {analysis_path}",
        f"- [ ] Save a copy of the analysis inside the cloned repo at {clone_path}/ANALYSIS.md",
    ]

    success_criteria = [
        f"- Repository cloned successfully to {clone_path}",
        f"- Analysis document generated at {analysis_path}",
        f"- Analysis copy saved inside cloned repo",
    ]

    task_content = f"""# Task: Analyze Repository - {repo.full_name}

**Task ID:** {task_id}
**Created:** {now.strftime('%Y-%m-%d %H:%M:%S')}
**Source:** link-sentinel (Telegram monitor)
**Priority:** {effective_priority}
**Project:** github-repo-analysis
**Type:** analysis
**Analysis-Depth:** {depth_cfg['depth']}
**Complexity-Score:** {depth_cfg['complexity_score']}

## Summary
{summary}

## Repository Information
- **URL:** {repo.url}
- **Owner:** {repo.owner}
- **Repository:** {repo.repo}
- **Clone URL:** {repo.clone_url}

## Paths
- **Clone to:** {clone_path}
- **Analysis doc:** {analysis_path}
- **In-repo copy:** {clone_path}/ANALYSIS.md

## Context
{chr(10).join(context_lines)}

## User Request
{user_prompt if user_prompt else "No specific request — perform general analysis."}

## Analysis Focus
{analysis_focus} ({depth_cfg['focus_hint']})

## Action Items
{chr(10).join(action_items)}

## Success Criteria
{chr(10).join(success_criteria)}

## Dynamic Agent Config
```json
{{
  "agent": "{agent}",
  "source": "agents/models/default/{agent}.json",
  "analysis_depth": "{depth_cfg['depth']}"
}}
```

---
**Target Agent:** {agent}
**Agent Available:** Yes
**Routing Confidence:** 95%
**Ready Status:** READY_FOR_EXECUTION
"""

    content_hash = generate_content_hash(task_content)
    task_content = task_content.replace("**Type:** analysis", f"**Type:** analysis\n**Content-Hash:** {content_hash}")

    return task_content


def _resolve_video_depth_config(analysis_depth: str) -> dict[str, str]:
    """Video equivalent of the repo depth resolver."""
    if analysis_depth == DETAILED_DEPTH:
        return {
            "depth": DETAILED_DEPTH,
            "agent": "scholar",
            "priority_bump": "High",
            "complexity_score": "75",
            "focus_hint": "deep (section-by-section, technical details, sources, counterpoints)",
        }
    return {
        "depth": STANDARD_DEPTH,
        "agent": "video-summarizer",
        "priority_bump": None,
        "complexity_score": "40",
        "focus_hint": "standard",
    }


def create_video_summary_task(
    video: YouTubeVideo,
    transcript_dir: Path,
    priority: str = "Medium",
    sender_name: Optional[str] = None,
    user_prompt: str = "",
    analysis_depth: str = STANDARD_DEPTH,
) -> str:
    """
    Create a task file content for YouTube video summarization.

    Args:
        video: Parsed YouTube video
        transcript_dir: Directory where transcripts are saved
        priority: Task priority (High, Medium, Low)
        sender_name: Telegram username who sent the link
        user_prompt: The prompt to send to the downstream agent
        analysis_depth: "standard" or "detailed" — picks agent + complexity

    Returns:
        Task file content as string
    """
    task_id = generate_task_id()
    now = datetime.now()
    depth_cfg = _resolve_video_depth_config(analysis_depth)
    effective_priority = depth_cfg["priority_bump"] or priority
    agent = depth_cfg["agent"]

    summary = f"Transcribe and summarize YouTube video {video.video_id} ({depth_cfg['depth']})"

    context_lines = [
        f"- Video URL: {video.url}",
        f"- Source: Telegram link monitor (link-sentinel)",
    ]
    if sender_name:
        context_lines.append(f"- Sent by: {sender_name}")

    transcript_path = transcript_dir / f"{video.folder_name}.txt"

    action_items = [
        f"- [ ] Fetch video transcript/subtitles",
        f"- [ ] Save raw transcript to {transcript_path}",
        f"- [ ] Identify key topics and themes",
        f"- [ ] Generate structured summary with main points",
        f"- [ ] Extract actionable insights or takeaways",
    ]

    success_criteria = [
        f"- Video transcript saved to {transcript_path}",
        f"- Summary generated with all key points",
        f"- Actionable insights extracted",
    ]

    task_content = f"""# Task: Summarize Video - {video.video_id}

**Task ID:** {task_id}
**Created:** {now.strftime('%Y-%m-%d %H:%M:%S')}
**Source:** link-sentinel (Telegram monitor)
**Priority:** {effective_priority}
**Project:** youtube-video-summary
**Type:** summary
**Analysis-Depth:** {depth_cfg['depth']}
**Complexity-Score:** {depth_cfg['complexity_score']}

## Summary
{summary}

## Video Information
- **URL:** {video.url}
- **Video ID:** {video.video_id}

## Paths
- **Transcript:** {transcript_path}

## Context
{chr(10).join(context_lines)}

## User Request
{user_prompt if user_prompt else "No specific request — provide general summary."}

## Analysis Focus
{depth_cfg['focus_hint']}

## Action Items
{chr(10).join(action_items)}

## Success Criteria
{chr(10).join(success_criteria)}

## Dynamic Agent Config
```json
{{
  "agent": "{agent}",
  "source": "agents/models/default/{agent}.json",
  "analysis_depth": "{depth_cfg['depth']}"
}}
```

---
**Target Agent:** {agent}
**Agent Available:** Yes
**Routing Confidence:** 95%
**Ready Status:** READY_FOR_EXECUTION
"""

    content_hash = generate_content_hash(task_content)
    task_content = task_content.replace("**Type:** summary", f"**Type:** summary\n**Content-Hash:** {content_hash}")

    return task_content


def write_task_file(
    task_content: str,
    folder_name: str,
    task_type: str,
    output_dir: Path,
) -> Path:
    """
    Write task file to the pipeline directory.

    Args:
        task_content: Task file content
        folder_name: Identifier for the filename
        task_type: Type prefix (repo_analysis, video_summary)
        output_dir: Directory to write task file

    Returns:
        Path to written task file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"task_{task_type}_{folder_name}.md"
    filepath = output_dir / filename

    filepath.write_text(task_content)
    return filepath
