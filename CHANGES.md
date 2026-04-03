# Changes — 2026-03-17

## YouTube transcription fix + forced PDF delivery

### Problem
- YouTube video transcription was completely broken inside the Docker container
- `yt-dlp` was not installed in the image — the transcript API fallback would fail for some videos, and the yt-dlp fallback didn't exist
- Claude CLI was not accessible inside the container (hardcoded host path, no mount) — even if transcription succeeded, summarization would have failed
- YouTube videos prompted the user for delivery format (msg vs PDF) unnecessarily

### Files changed

**Dockerfile**
- Added `ffmpeg` to system dependencies
- Added `yt-dlp` via pip install

**docker-compose.yml**
- Mounted Node.js runtime (`/opt/node`) and Claude config (`~/.claude`) into container (read-only)
- Added `CLAUDE_PATH` and `PATH` environment variables pointing to mounted Node.js/Claude

**src/video_processor.py**
- `CLAUDE_PATH` now reads from `CLAUDE_PATH` env var, falls back to host path for local dev

**src/bot.py**
- YouTube videos no longer show format choice buttons — always processed immediately as PDF
- `_process_video` updated to work without a callback query (direct invocation from `handle_message`)
- Removed video branch from callback handler since videos no longer go through callbacks

**start.sh** (created)
- Docker startup script that runs in background and logs to `./logs/link-sentinel.log`

**~/.local/bin/dictation-scripts/pipeline-ensure.sh** (modified, outside repo)
- Added Docker Services section that starts link-sentinel container if not running
- Includes log file setup on cold start
