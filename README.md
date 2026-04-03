# Link Sentinel

GitHub link monitor for the AI Task Automation pipeline. Monitors a Telegram channel for GitHub repository URLs and automatically creates analysis tasks.

## Overview

Link Sentinel watches a designated Telegram channel for GitHub repository links. When a link is detected, it:

1. Parses the GitHub URL to extract owner and repository name
2. Generates a task file in the AI Task Automation pipeline format
3. Writes the task to `data/pipeline/transposed/` for processing
4. The pipeline's `repo-analyzer` agent then clones and analyzes the repository
5. Optionally, the `repo-comparator` agent compares it against existing projects

## Quick Start

### 1. Create Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Add your bot to the channel you want to monitor
5. Make the bot an admin (so it can read messages)

### 2. Get Channel ID

1. Forward any message from your channel to [@userinfobot](https://t.me/userinfobot)
2. The bot will reply with the channel ID (negative number like `-1001234567890`)

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your values
nano .env
```

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Your bot token from BotFather
- `TELEGRAM_CHANNEL_ID` - Your channel ID (negative number)

### 4. Run with Docker

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 5. Run Locally (Development)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

## Usage

### Automatic Detection

Simply paste any GitHub URL in the monitored channel:

```
https://github.com/anthropics/anthropic-cookbook
```

Link Sentinel will automatically:
- Detect the link
- Create an analysis task
- Notify you in the channel

### Manual Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | Show available commands |
| `/status` | Check bot configuration |
| `/analyze <url> [target]` | Manually trigger analysis with optional comparison target |

Examples:
```
/analyze https://github.com/owner/repo
/analyze https://github.com/owner/repo ai-task-automation
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Bot token from BotFather |
| `TELEGRAM_CHANNEL_ID` | Yes | - | Channel ID to monitor |
| `DEFAULT_COMPARISON_TARGET` | No | `ai-task-automation` | Default project for comparisons |
| `AUTO_ANALYZE` | No | `true` | Auto-detect links in messages |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `PIPELINE_TRANSPOSED_DIR` | No | (see below) | Pipeline output directory |
| `REPO_ANALYSIS_DIR` | No | (see below) | Repo analysis root directory |

Default paths (can be overridden):
- `PIPELINE_TRANSPOSED_DIR`: `/home/shaddar/Documents/workspace/ai-task-automation/data/pipeline/transposed`
- `REPO_ANALYSIS_DIR`: `/home/shaddar/Documents/workspace/personal/projects/github/repo-analysis`

## Pipeline Integration

### Task Flow

```
Telegram Channel
     │
     ▼
Link Sentinel (detects GitHub URLs)
     │
     ▼
Creates task file in pipeline/transposed/
     │
     ▼
Orchestrator-v1 (enriches task)
     │
     ▼
Orchestrator-v2 (routes to repo-analyzer agent)
     │
     ▼
Task Executor (spawns repo-analyzer)
     │
     ▼
repo-analyzer clones and analyzes
     │
     ▼ (if comparison target specified)
repo-comparator generates comparison report
```

### Generated Task Format

Tasks are created with:
- Target agent: `repo-analyzer`
- Output locations:
  - Analysis: `$PPROJECTS/github/repo-analysis/analysis-docs/{owner}_{repo}_analysis.md`
  - Comparison: `$PPROJECTS/github/repo-analysis/comparisons/{owner}_{repo}_vs_{target}_comparison.md`

## Project Structure

```
link-sentinel/
├── src/
│   ├── __init__.py
│   ├── bot.py           # Telegram bot implementation
│   ├── config.py        # Settings management
│   ├── github_parser.py # GitHub URL parsing
│   └── task_generator.py # Pipeline task generation
├── tests/
├── main.py              # Entry point
├── requirements.txt     # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── .env.example        # Example configuration
└── README.md
```

## Supported URL Formats

Link Sentinel recognizes these GitHub URL patterns:

- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `http://github.com/owner/repo`
- `github.com/owner/repo`
- `git@github.com:owner/repo.git`
- URLs with trailing paths, hashes, or query params

## Troubleshooting

### Bot not responding

1. Check bot is admin in channel
2. Verify channel ID is correct (negative number)
3. Check logs: `docker-compose logs -f`

### Tasks not appearing in pipeline

1. Verify volume mounts in docker-compose.yml
2. Check pipeline/transposed directory permissions
3. Ensure paths match your system

### GitHub URLs not detected

1. Ensure URL is on its own line or clearly separated
2. Try the `/analyze` command manually
3. Check logs for parsing errors

## Development

### Running Tests

```bash
pytest tests/
```

### Adding New Features

1. URL formats: Edit `src/github_parser.py`
2. Task format: Edit `src/task_generator.py`
3. Bot commands: Edit `src/bot.py`

## Related Components

- **repo-analyzer agent**: `agents/models/sonnet-4.5/repo-analyzer.json`
- **repo-comparator agent**: `agents/models/sonnet-4.5/repo-comparator.json`
- **Analysis output**: `$PPROJECTS/github/repo-analysis/`
- **Pipeline docs**: `docs/SYSTEM-MAP.md`
