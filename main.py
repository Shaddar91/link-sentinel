#!/usr/bin/env python3
"""Link Sentinel - GitHub Link Monitor for AI Task Automation Pipeline.

Monitors a Telegram channel for GitHub repository links and automatically
creates analysis tasks for the AI Task Automation pipeline.
"""
import asyncio
import sys
from pathlib import Path

#Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import main

if __name__ == "__main__":
    asyncio.run(main())
