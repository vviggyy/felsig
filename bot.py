import asyncio
import sqlite3
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import os
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load env variables
load_dotenv()

# Database setup
DB_PATH = os.path.expanduser("~/telegram_daily_messages.db")

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            text TEXT,
            processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def store_message(text, timestamp):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (timestamp, text) VALUES (?, ?)", (timestamp.isoformat(), text))
    conn.commit()
    conn.close()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Starting..."
    )

async def daily_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = ' '.join(context.args)
    if not msg.strip(): #message is empty
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please provide a message after /dn."
        )
        return

    try:
        store_message(msg, update.message.date)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Saved for daily note!"
        )
    except Exception as e:
        logging.error(f"Exception: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Something went wrong."
        )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Command unknown"
    )

# Main setup
if __name__ == "__main__":
    setup_db()

    application = ApplicationBuilder().token(os.getenv("API_KEY")).build()

    start_handler = CommandHandler("start", start)
    daily_note_handler = CommandHandler("dn", daily_note)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)

    application.add_handler(start_handler)
    application.add_handler(daily_note_handler)
    application.add_handler(unknown_handler)

    application.run_polling()
