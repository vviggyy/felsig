#!/bin/bash

PYTHON="/Users/viggy/mambaforge/bin/python"
BOT_SCRIPT="bot.py"
LOGFILE="$HOME/telegram_bot.log"

# Start bot in background, redirect output
echo "starting bot..."
$PYTHON "$BOT_SCRIPT" >> "$LOGFILE" 2>&1 &

BOT_PID=$!
sleep 10
echo "killing bot..."
kill $BOT_PID
