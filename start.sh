#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

LOG_DIR="./logs"
LOG_FILE="${LOG_DIR}/link-sentinel.log"
mkdir -p "$LOG_DIR"

docker-compose up -d --build

echo "Link Sentinel started. Logging to ${LOG_FILE}"
echo "---"
echo "  Tail logs:  tail -f ${LOG_FILE}"
echo "  Stop:       docker-compose down"

# Follow logs to file in background
nohup docker-compose logs -f --no-color >> "$LOG_FILE" 2>&1 &
