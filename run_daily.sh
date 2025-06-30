#!/bin/bash

# File to track last run date
LAST_RUN_FILE=~/last_run_date.txt
TODAY=$(date +%Y-%m-%d)

# Only run if not run today
if [ ! -f "$LAST_RUN_FILE" ] || [ "$(cat $LAST_RUN_FILE)" != "$TODAY" ]; then
    echo "Running daily script at $(date)" >> ~/launchd_run.log

    /Users/viggy/Desktop/rt/Misc/felsig/automate.sh #run automation script

    # Update last run date
    echo "$TODAY" > "$LAST_RUN_FILE"
else
    echo "Already ran today, skipping $(date)" >> ~/launchd_run.log
fi
