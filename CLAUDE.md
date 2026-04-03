# Link Sentinel

## Location
`/home/shaddar/Documents/workspace/personal/projects/link-sentinel/`

## Purpose
Telegram bot that monitors a channel for GitHub repository links and YouTube video links, then creates appropriate tasks for the AI Task Automation pipeline.

## Tech Stack
- Python 3.12
- python-telegram-bot (async)
- pydantic-settings
- structlog
- Docker/docker-compose

## Key Files
- `src/bot.py` - Telegram bot implementation
- `src/github_parser.py` - GitHub URL extraction/parsing
- `src/youtube_parser.py` - YouTube URL extraction/parsing
- `src/task_generator.py` - Pipeline task file generation (repo analysis + video summary)
- `src/config.py` - Settings from environment

## Integration Points
- **Input**: Telegram channel messages containing GitHub URLs or YouTube links
- **Output**: Task files in `data/pipeline/transposed/` format
- **GitHub Agent**: Routes to `repo-analyzer`
- **YouTube Agent**: Routes to `video-summarizer`
- **Transcripts**: Saved to `~/.transcribes` (shared with `trans` alias / transcribe.py)

## Quick Commands
```bash
#Start service
docker-compose up -d

#View logs
docker-compose logs -f

#Stop
docker-compose down

#Local dev
python main.py
```

## Environment Variables
- `TELEGRAM_BOT_TOKEN` - Required
- `TELEGRAM_CHANNEL_ID` - Required
- `GITHUB_CLONE_DIR` - Default: ~/Documents/workspace/personal/projects/github/repo-analysis/cloned
- `GITHUB_ANALYSIS_DIR` - Default: ~/Documents/workspace/personal/projects/github/repo-analysis/analysis-docs
- `YOUTUBE_TRANSCRIPT_DIR` - Default: ~/.transcribes
- `PIPELINE_TRANSPOSED_DIR` - Default: ~/Documents/workspace/ai-task-automation/data/pipeline/transposed
- `AUTO_ANALYZE` - Default: true
