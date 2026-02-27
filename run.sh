#!/bin/zsh
# run.sh — Wrapper script for the stock-weekly-report pipeline.
#
# Sources ~/.zprofile so that EMAIL_SMTP_PASSWORD and other env vars
# are available even when invoked from cron (which runs with a bare environment).
#
# Crontab entry (every Sunday at 8:00 AM):
#   0 8 * * 0 /Users/yuchuan/Projects/stock-weekly-report/run.sh

source ~/.zprofile

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/pipeline.log"
mkdir -p "$SCRIPT_DIR/logs"

echo "======================================" >> "$LOG_FILE"
echo "Run started: $(date)" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"

"$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/pipeline.py" "$@" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}
echo "" >> "$LOG_FILE"
echo "Run finished: $(date) (exit $EXIT_CODE)" >> "$LOG_FILE"

exit $EXIT_CODE
