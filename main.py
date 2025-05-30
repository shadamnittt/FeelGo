from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = ApplicationBuilder().token(BOT_TOKEN).build()

# Пример команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет, я твой бот!")

app.add_handler(CommandHandler("start", start))

app.run_polling()
