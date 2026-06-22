import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# TOKEN (ЖЁСТКАЯ ПРОВЕРКА)
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ TELEGRAM_TOKEN NOT FOUND IN ENV")
    raise SystemExit()

# =========================
# LOGS
# =========================
logging.basicConfig(level=logging.INFO)

print("BOT STARTED OK")

# =========================
# MEMORY
# =========================
USER = {}

# =========================
# LOGIC
# =========================
def get_connector(mode):
    return {
        "free": ["PRO улучшение", "Вакансии", "HR интервью"],
        "pro": ["VIP резюме", "Сайт-визитка", "Анализ рынка"],
        "vip": ["VIP стратегия", "CEO интервью", "Закрытие позиции"]
    }.get(mode, [])

# =========================
# START COMMAND
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("FREE", callback_data="free")],
        [InlineKeyboardButton("PRO", callback_data="pro")],
        [InlineKeyboardButton("VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "🚀 CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    mode = q.data
    USER[q.from_user.id] = mode

    await q.message.reply_text(f"✅ {mode.upper()} MODE ACTIVE")

    steps = get_connector(mode)

    for step in steps:
        await q.message.reply_text("➡️ " + step)

# =========================
# MAIN
# =========================
def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    print("RUNNING...")

    app.run_polling()

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
