import asyncio
from dotenv import load_dotenv
from telegram import Update #base API
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters # python telegram bot API
import os
import logging
from datetime import date

logging.basicConfig(
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', #formatting of the logging message
    level = logging.INFO
)

#load env variables
load_dotenv()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): #update contains information colelcted about the new update from telegram, and context contains the library items like the Bot
    await context.bot.send_message( #why no "with" statement here?
        chat_id = update.effective_chat.id,
        text = "Starting..."
    )

#adds message after /dn to daily notes
async def daily_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sep = ' '
    msg = sep.join(context.args)
    td_date = str(date.today())
    try:
        with open(os.getenv("OBS_PATH") + "/" + td_date + ".md", "a") as file:
            file.write("\n" + msg)
        await context.bot.send_message(
            chat_id = update.effective_chat.id,
            text = "Sent to Obsidian Daily Note!"
        )
    except Exception as e:
        print(f"An Exception has occured: {e}")
    
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id = update.effective_chat.id, 
        text = "Command unknown")
    
if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("API_KEY")).build() #create application on the token...
    
    start_handler = CommandHandler("start", start) #manage start command
    daily_note_handler = CommandHandler("dn", daily_note)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    
    application.add_handler(start_handler) # add start_handler 
    application.add_handler(daily_note_handler)
    application.add_handler(unknown_handler)
    
    application.run_polling()
    