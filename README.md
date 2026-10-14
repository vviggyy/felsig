vibecoded bot that captures notes-to-self in telegram and writes them to obsidian

in German: rocky

## what it does

| send                                           | lands in                   |
| ---------------------------------------------- | -------------------------- |
| plain text, `/dn`, `!dn`                       | `OP3R/daily/YYYY-MM-DD.md` |
| `/idea`, `!idea`                               | `ideas/inbox.md`           |
| `/learn`, `!learn`                             | `to learn.md`              |
| voice note                                     | daily note, transcribed    |
| voice note starting "idea, ..." / "learn, ..." | that target                |

Entries are dated by when you *sent* them (`- 14:32 text` in the daily note, `- [[2026-10-14]] text` elsewhere, linking back to the day). The bot replies ✓ with where it went.

Voice notes are transcribed locally with [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (large-v3-turbo, quantized, on the Mac's GPU): free, offline, ~4s per note (the very first one took ~30s while macOS cached the model). The reply includes the transcript so you can catch mishearings. Routing keys off the first word, so pause after it ("Idea. ..."), and a daily note that happens to start with "Ideas are..." will go to ideas.

## how it runs

```
phone ──► Telegram's servers ◄──── bot.py on the Mac ────► ~/Documents/vvv
          (hold messages            (long-polls: "anything
           up to 24h)                new?", always running)
```

One process (`bot.py`) runs all the time under launchd, which starts it at login and restarts it if it crashes. It long-polls Telegram and appends straight to the vault. Only your Telegram user ID (`ALLOWED_USER_ID`) can write.

**Lid closed:** the bot is frozen and messages wait on Telegram's servers. When the Mac wakes, it catches up and writes everything with the original send time, so nothing lands on the wrong day. You just get the ✓ late. Telegram drops messages after **24h**, so a weekend with the lid shut loses Friday's notes; the heartbeat below warns you before that happens.

### when it can't save

It never fails silently:

- **Write fails** (permissions, disk full): ⚠️ reply with the reason. The entry is queued in `~/.felsig/pending.jsonl` and written on the next message or restart. If even the queue can't be written, the reply says **NOT saved**.
- **Transcription fails** or anything unexpected breaks: ⚠️ reply saying it wasn't saved.
- **Mac asleep/off:** the bot can't reply, so no ✓ means it's offline. Set `HEARTBEAT_URL` and [healthchecks.io](https://healthchecks.io) (free) alerts you when the bot has been quiet too long (see setup).

## setup

```sh
./felsig.sh setup         # deps (venv in ~/.felsig/venv), creates .env + config.toml
                          # put the token from @BotFather (/mybots -> API Token) in .env
./felsig.sh voice         # whisper.cpp + model (~550MB in ~/.felsig/models)
./felsig.sh run           # try it in the terminal: message the bot, it replies with your
                          # user ID -> put it in .env as ALLOWED_USER_ID, Ctrl-C, run again
                          # Ctrl-C again when done testing: only one copy can run at a time
./felsig.sh start         # install + start the always-on launchd service
```

Then send one message. If the bot replies that **macOS blocked writing to the vault**, see the permissions section below.

**Offline alert (optional, 2 min):** on healthchecks.io create a check with *period 1 hour, grace 17 hours* (alerts at 18h offline, before Telegram's 24h cutoff), add the Telegram integration to get alerts there, paste the ping URL into `.env` as `HEARTBEAT_URL=`, then `./felsig.sh restart`. The bot checks in every 10 min and healthchecks also tells you when it's back.

### day to day

```sh
./felsig.sh status        # running? pid, last exit code
./felsig.sh logs          # follow ~/Library/Logs/felsig.log
./felsig.sh restart       # after editing .env, config.toml, or bot.py
./felsig.sh stop          # stop until next login (rm ~/Library/LaunchAgents/com.vviggyy.felsig.plist to remove for good)
```

### adding a target

Add a block to `config.toml` and `./felsig.sh restart`. This gives you `/biz`, `!biz`, `/business`, and a spoken "biz, ...":

```toml
[targets.biz]
path = "venture/business ideas.md"   # strftime codes allowed, e.g. "log/%Y-%m.md"
entry = "- [[{date}]] {text}"        # {date} {time} {text}
label = "business ideas"
aliases = ["business"]
```

Plain text and untagged voice notes go to `default` (the daily note). Voice language, model, and the 🎙 marker are under `[voice]`.

### the permissions thing

macOS blocks background processes from touching `~/Documents` and `~/Desktop` (where the vault and this repo live) unless they're allowed. This is what broke the old launchd/cron/Shortcuts attempts. If the bot reports it, run `./felsig.sh permissions`: it copies the Python path and opens Full Disk Access. Click +, Cmd+Shift+G, paste, Open, then `./felsig.sh restart`. Queued notes get written then.

Caveat: that grants access to uv's shared Python 3.12 binary, so it applies to anything run with it. If uv upgrades Python (the path changes), grant it again.

## troubleshooting

- **`Conflict: terminated by other getUpdates request`** / "another copy of this bot is polling": two copies are running (usually `run` in a terminal while the service is up). Ctrl-C the terminal one. `run` refuses to start while the service is loaded.
- **No ✓ reply:** Mac asleep, offline, or the bot is down. `./felsig.sh status` and `./felsig.sh logs`.
- **Bot ignores you:** `ALLOWED_USER_ID` in `.env` doesn't match; clear it, restart, and message the bot to get your ID.

## where things live

| what | where |
| --- | --- |
| code, `.env`, `config.toml` | this repo (`.env` and `config.toml` are gitignored) |
| Python venv | `~/.felsig/venv` (outside `~/Desktop` so launchd can run it) |
| whisper model | `~/.felsig/models/` |
| retry queue | `~/.felsig/pending.jsonl` |
| log | `~/Library/Logs/felsig.log` |
| launchd service | `~/Library/LaunchAgents/com.vviggyy.felsig.plist` |
