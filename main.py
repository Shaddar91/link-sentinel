#!/usr/bin/env python3
"""Link Sentinel - GitHub Link Monitor for AI Task Automation Pipeline.

Monitors a Telegram channel for GitHub repository links and automatically
creates analysis tasks for the AI Task Automation pipeline.
"""
import asyncio
import shutil
import sys
from pathlib import Path

#Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import main


def _bootstrap_claude_config() -> None:
    """Restore $HOME/.claude.json from the latest backup if missing.

    Claude CLI stores config at $HOME/.claude.json. The container's copy is
    lost on every image rebuild, but the host-mounted $HOME/.claude/backups/
    directory holds recent snapshots. Copying the latest keeps the CLI
    functional across rebuilds without exposing the host's live .claude.json.
    """
    home = Path.home()
    config = home / ".claude.json"
    if config.exists():
        print(f"[bootstrap] .claude.json already present at {config}", file=sys.stderr)
        return

    backups_dir = home / ".claude" / "backups"
    if not backups_dir.exists():
        print(f"[bootstrap] No backups dir at {backups_dir}", file=sys.stderr)
        return

    backups = sorted(backups_dir.glob(".claude.json.backup.*"))
    if not backups:
        print(f"[bootstrap] No backups found in {backups_dir}", file=sys.stderr)
        return

    latest = backups[-1]
    shutil.copy2(latest, config)
    print(f"[bootstrap] Restored .claude.json from {latest.name}", file=sys.stderr)


if __name__ == "__main__":
    _bootstrap_claude_config()
    asyncio.run(main())
