"""felsig: Telegram -> Obsidian capture bot.

Long-polls Telegram and appends every message from you to a note in your vault:
  plain text, /dn, !dn       -> today's daily note
  /idea, !idea               -> ideas inbox
  /learn, !learn             -> things to learn
  voice notes                -> transcribed locally with whisper.cpp, then routed the same way
                                (start the recording with "idea ..." or "learn ..." to route it)
Targets live in config.toml (see config.example.toml).
"""
import asyncio
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

import av
from dotenv import load_dotenv
from telegram import BotCommand, Message, Update
from telegram.error import Conflict
from telegram.ext import Application, ContextTypes, MessageHandler, filters

ROOT = Path(__file__).resolve().parent
STATE_DIR = Path.home() / ".felsig"
PENDING = STATE_DIR / "pending.jsonl"  # entries that couldn't be written to the vault yet

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # otherwise every getUpdates poll is logged
log = logging.getLogger("felsig")

load_dotenv(ROOT / ".env")
CONFIG = tomllib.loads(Path(os.getenv("FELSIG_CONFIG", ROOT / "config.toml")).read_text())
VAULT = Path(CONFIG["vault"]).expanduser()
TARGETS: dict[str, dict] = CONFIG["targets"]
DEFAULT = CONFIG.get("default", "dn")
VOICE = CONFIG.get("voice", {})
ALIASES = {name: name for name in TARGETS} | {
    alias: name for name, t in TARGETS.items() for alias in t.get("aliases", [])
}
ALLOWED = {int(x) for x in os.getenv("ALLOWED_USER_ID", "").replace(",", " ").split()}

PREFIX = re.compile(r"[/!](\w+)(?:@\w+)?(?:\s+|$)(.*)", re.DOTALL)  # "/idea text", "!idea text", "/idea@bot text"
SPOKEN = re.compile(r"\W*(\w+)[\s,.:;!?-]+(.+)", re.DOTALL)  # "Idea, text" at the start of a transcript
NON_SPEECH = re.compile(r"\[[A-Z_ ]+\]")  # whisper.cpp markers like [BLANK_AUDIO]


# --- writing to the vault ---------------------------------------------------

def render(key: str, text: str, when) -> tuple[Path, str]:
    """Build the note path and the line(s) to append for a message sent at `when`."""
    target = TARGETS[key]
    first, *rest = [line.rstrip() for line in text.strip().splitlines()]
    body = "\n".join([first] + [f"  {line}" if line else "" for line in rest])  # keep multi-line text in one bullet
    entry = target.get("entry", "- {text}").format(
        date=when.strftime("%Y-%m-%d"), time=when.strftime("%H:%M"), text=body
    )
    return VAULT / when.strftime(target["path"]), entry


def append(path: Path, entry: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab+") as f:
        size = f.seek(0, os.SEEK_END)
        needs_newline = size > 0 and (f.seek(-1, os.SEEK_END), f.read(1))[1] != b"\n"
        f.write((("\n" if needs_newline else "") + entry + "\n").encode())


def flush_pending():
    if not PENDING.exists():
        return
    left = []
    for line in PENDING.read_text().splitlines():
        item = json.loads(line)
        try:
            append(Path(item["path"]), item["entry"])
        except OSError:
            left.append(line)
    if left:
        PENDING.write_text("\n".join(left) + "\n")
    else:
        PENDING.unlink()
        log.info("flushed retry queue")


def save(path: Path, entry: str):
    """Append to the vault; on failure queue the entry in ~/.felsig and re-raise."""
    flush_pending()
    try:
        append(path, entry)
    except OSError:
        STATE_DIR.mkdir(exist_ok=True)
        with PENDING.open("a") as f:
            f.write(json.dumps({"path": str(path), "entry": entry}) + "\n")
        raise


async def store(msg: Message, key: str, text: str) -> str:
    """Save text to target `key`, dated by when the message was sent. Returns a reply for the chat."""
    path, entry = render(key, text, msg.date.astimezone())
    try:
        save(path, entry)
    except PermissionError:
        log.exception("vault write blocked")
        return (
            "⚠️ macOS blocked writing to the vault. Give Full Disk Access to "
            f"{os.path.realpath(sys.executable)} (./felsig.sh permissions), then ./felsig.sh restart. "
            "Your note is queued and will be written once that's fixed."
        )
    except OSError as e:
        log.exception("vault write failed")
        return f"⚠️ Couldn't write to the vault ({e.strerror}). Queued; will retry on the next message."
    log.info("saved to %s", path.relative_to(VAULT))
    return f"✓ {TARGETS[key].get('label', key)}"


# --- voice ------------------------------------------------------------------

def to_wav(src: Path, dst: Path):
    """Decode any audio (Telegram voice notes are OGG/Opus) to the 16 kHz mono WAV whisper.cpp expects."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    with av.open(str(src)) as inp, av.open(str(dst), "w", format="wav") as out:
        stream = out.add_stream("pcm_s16le", rate=16000, layout="mono")
        for frame in inp.decode(audio=0):
            for f in resampler.resample(frame):
                out.mux(stream.encode(f))
        for f in resampler.resample(None):
            out.mux(stream.encode(f))
        out.mux(stream.encode(None))


async def transcribe(audio: Path) -> str:
    cli = shutil.which("whisper-cli", path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    model = Path(VOICE.get("model", "~/.felsig/models/ggml-large-v3-turbo-q5_0.bin")).expanduser()
    if not cli or not model.exists():
        raise RuntimeError("voice isn't set up yet, run ./felsig.sh voice")
    wav = audio.with_suffix(".wav")
    await asyncio.to_thread(to_wav, audio, wav)
    proc = await asyncio.create_subprocess_exec(
        cli, "-m", str(model), "-f", str(wav), "-l", VOICE.get("language", "en"), "-nt", "-np",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"whisper-cli exited {proc.returncode}: {err.decode()[-300:]}")
    # whisper sometimes starts segments with subtitle-style dialogue dashes ("- Idea, ...")
    lines = (line.strip().lstrip("-–— ") for line in NON_SPEECH.sub("", out.decode()).splitlines())
    return " ".join(" ".join(lines).split())


def route_spoken(text: str) -> tuple[str, str]:
    """'Idea, an app that ...' -> ('idea', 'An app that ...'); anything else goes to the default target."""
    m = SPOKEN.match(text)
    if m and m[1].lower() in ALIASES:
        body = m[2].strip()
        return ALIASES[m[1].lower()], body[:1].upper() + body[1:]
    return DEFAULT, text


# --- telegram handlers ------------------------------------------------------

def help_text() -> str:
    lines = ["Send me text or a voice note.", ""]
    for name, t in TARGETS.items():
        cmds = ", ".join(f"/{a} !{a}" for a in [name, *t.get("aliases", [])])
        lines.append(f"{cmds} → {t['path']}" + ("  (default)" if name == DEFAULT else ""))
    spoken = " / ".join(f'"{name}"' for name in TARGETS if name != DEFAULT)
    lines += ["", f"Plain text goes to the default. Start a voice note with {spoken} to route it."]
    return "\n".join(lines)


async def allowed(update: Update) -> bool:
    uid = update.effective_user.id
    if uid in ALLOWED:
        return True
    if not ALLOWED:
        await update.message.reply_text(
            f"Your Telegram user ID is {uid}.\n"
            f"Add ALLOWED_USER_ID={uid} to .env and run ./felsig.sh restart. Nothing is saved until then."
        )
    else:
        log.warning("ignoring message from user %s", uid)
    return False


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not await allowed(update):
        return
    m = PREFIX.match(msg.text)
    cmd = m[1].lower() if m else None
    if cmd in ("start", "help"):
        await msg.reply_text(help_text())
        return
    if cmd in ALIASES:
        key, body = ALIASES[cmd], m[2]
    elif m and msg.text.startswith("/"):
        await msg.reply_text(f"Unknown command /{cmd}.\n\n{help_text()}")
        return
    else:  # plain text, or "!word" that isn't a target
        key, body = DEFAULT, msg.text
    if not body.strip():
        await msg.reply_text(f"Nothing to save. Usage: /{key} <text>")
        return
    await msg.reply_text(await store(msg, key, body))


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not await allowed(update):
        return
    media = msg.voice or msg.audio or msg.video_note
    status = await msg.reply_text("🎙 transcribing…")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "audio"
            await (await media.get_file()).download_to_drive(src)
            text = await transcribe(src)
    except Exception as e:
        log.exception("transcription failed")
        await status.edit_text(f"⚠️ Couldn't transcribe: {e}\nNothing was saved; resend it once fixed.")
        return
    if not text:
        await status.edit_text("🤷 Didn't catch any speech, nothing saved.")
        return
    m = PREFIX.match(msg.caption or "")  # forwarded audio can carry a "/idea" caption
    key, body = (ALIASES[m[1].lower()], text) if m and m[1].lower() in ALIASES else route_spoken(text)
    reply = await store(msg, key, VOICE.get("prefix", "🎙 ") + body)
    await status.edit_text(f"{reply}\n\n{body}"[:4000])


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        log.error("another copy of this bot is polling with the same token (./felsig.sh run and start at once?)")
    else:
        log.error("unhandled error", exc_info=context.error)


async def post_init(app: Application):
    commands = [BotCommand(name, t.get("label", t["path"])) for name, t in TARGETS.items()]
    await app.bot.set_my_commands(commands + [BotCommand("help", "what goes where")])
    flush_pending()


def main():
    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("API_KEY")
    if not token:
        sys.exit("TELEGRAM_TOKEN missing from .env")
    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT, on_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, on_voice))
    app.add_error_handler(on_error)
    log.info("felsig polling, vault=%s", VAULT)
    # Only new messages (not edits). Telegram holds unread messages for 24h, so anything
    # sent while the Mac was asleep arrives on wake.
    app.run_polling(allowed_updates=[Update.MESSAGE])


if __name__ == "__main__":
    main()
