import os
from dotenv import load_dotenv

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://pipis-tt66.vercel.app/")

if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN. Проверь файл .env")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Кнопка, которая открывает Mini App
    button = KeyboardButton(
        text="🌐 Открыть переводчик",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[button]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы открыть переводчик (Mini App).",
        reply_markup=keyboard
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/start — открыть кнопку Mini App\n"
        "/help — помощь"
    )

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    print("Бот запущен. Открой Telegram и напиши /start.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
