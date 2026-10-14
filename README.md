vibecoded bot that captures notes-to-self in telegram and writes them to obsidian

in German: rocky

## what it does

| send                                   | lands in                        |
| -------------------------------------- | ------------------------------- |
| plain text, `/dn`, `!dn`               | `OP3R/daily/YYYY-MM-DD.md`      |
| `/idea`, `!idea`                       | `ideas/inbox.md`                |
| `/learn`, `!learn`                     | `to learn.md`                   |
| voice note                             | daily note, transcribed         |
| voice note starting "idea, ..." / "learn, ..." | that target                  |

Entries are dated by when you *sent* them (`- 14:32 text` in the daily note, `- [[2026-10-14]] text` elsewhere). Targets are defined in `config.toml`; adding `/biz` or `/todo` is three lines.

Voice notes are transcribed locally with [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (large-v3-turbo, quantized, Metal GPU): free, offline, about 4s per note. The bot replies with the transcript so you can catch mishearings.

## how it runs

One long-running process (`bot.py`) long-polls Telegram and appends straight to the vault. launchd keeps it alive and starts it at login. Telegram holds unread messages for 24h, so anything sent while the Mac sleeps arrives when it wakes (more than 24h off and they're dropped).

Only your Telegram user ID (`ALLOWED_USER_ID`) can write. If a write fails, the entry goes to `~/.felsig/pending.jsonl` and is retried on the next message.

## setup

```sh
./felsig.sh setup         # deps (venv in ~/.felsig/venv), creates .env + config.toml
# put the token from @BotFather in .env
./felsig.sh voice         # whisper.cpp + model (~550MB in ~/.felsig/models)
./felsig.sh run           # try it in the terminal; message the bot to get your user ID,
                          # put it in .env as ALLOWED_USER_ID, Ctrl-C, run again
./felsig.sh start         # install + start the launchd service
./felsig.sh permissions   # one-time: give Python Full Disk Access (see below)
./felsig.sh logs | status | restart | stop
```

### the permissions thing

macOS blocks background processes from touching `~/Documents` and `~/Desktop` (where the vault and this repo live) unless the binary has Full Disk Access. This is what broke the old launchd/cron/Shortcuts attempts. `./felsig.sh permissions` copies the Python path and opens the settings pane: click +, Cmd+Shift+G, paste, Open, then `./felsig.sh restart`.

Caveat: that grants FDA to uv's shared Python 3.12 binary, so it applies to anything run with it. If uv upgrades Python (the path changes), grant it again.
