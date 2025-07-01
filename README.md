**felsig**
in German: rocky
vibecoded bot that captures notes-to-self in telegram and writes them to obsidian daily notes

The bot is a daemon controlled via `launchd`. When active, the daemon will launch `run_daily.sh` every 5 mins. This:
* runs `bot.py` for 60s, polling all previously sent messages when the bot was not running
* kills the bot
* runs `process_daily_notes.py` to send unprocessed messages to obsidian daily note

`plist` isn't shown here
