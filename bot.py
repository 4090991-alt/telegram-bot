import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ NO TOKEN FOUND")
    exit()

logging.basicConfig(level=logging.INFO)

print("BOT STARTED OK")

USER = {}

def get_connector(mode):
    return {
        "free": ["PRO улучшение", "Вакансии", "HR интервью"],
        "pro": ["VIP резюме", "Сайт-визитка", "Анализ рынка"],
        "vip": ["VIP стратегия", "CEO интервью", "Закрытие позиции"]
    }.get(mode, [])

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("FREE", callback_data="free")],
        [InlineKeyboardButton("PRO", callback_data="pro")],
        [InlineKeyboardButton("VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "🚀 CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()

    mode = q.data
    USER[q.from_user.id] = mode

    await q.message.reply_text(f"✅ {mode.upper()} MODE ACTIVE")

    steps = get_connector(mode)

    for step in steps:
        await q.message.reply_text("➡️ " + step)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    print("RUNNING...")

    # 💣 ВАЖНО: защита от конфликтов Telegram
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
