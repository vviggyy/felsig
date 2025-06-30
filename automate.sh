#!/bin/bash

echo "starting script" 
python /Users/viggy/Desktop/rt/Misc/felsig/bot.py & 
BOT=$!
sleep 60
kill $BOT
