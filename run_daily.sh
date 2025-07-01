#!/bin/bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] run_daily.sh triggered" >> "$HOME/run_daily.log"

# Full path to automate and processing scripts
AUTOMATE_SCRIPT="/Users/viggy/Desktop/rt/Misc/felsig/automate.sh"
PROCESS_SCRIPT="/Users/viggy/Desktop/rt/Misc/felsig/process_daily_notes.py"
PYTHON="/Users/viggy/mambaforge/bin/python"

TIMESTAMP="[$(date '+%Y-%m-%d %H:%M:%S')]"

#run the bot for 60s then kill. this collects any prev msgs and adds to sqlite db
echo "$TIMESTAMP Starting automate.sh to collect new Telegram messages..."
bash "$AUTOMATE_SCRIPT"

#send unprocessed notes to obsidian daily notes
TIMESTAMP="[$(date '+%Y-%m-%d %H:%M:%S')]"
echo "$TIMESTAMP Starting process_daily_notes.py to sync to Obsidian..."
"$PYTHON" "$PROCESS_SCRIPT" >> "$HOME/process_daily_notes.log" 2>&1

TIMESTAMP="[$(date '+%Y-%m-%d %H:%M:%S')]"
echo "$TIMESTAMP Finished sync."
