import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# LOAD ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ TOKEN NOT FOUND")
    exit()

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

print("🚀 BOT STARTED OK")

# =========================
# MEMORY
# =========================
USER = {}

# =========================
# LOGIC
# =========================
def get_connector(mode):
    data = {
        "free": ["PRO улучшение", "Вакансии", "HR интервью"],
        "pro": ["VIP резюме", "Сайт-визитка", "Анализ рынка"],
        "vip": ["VIP стратегия", "CEO интервью", "Закрытие позиции"]
    }
    return data.get(mode, [])

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
# HANDLER
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    mode = q.data
    user_id = q.from_user.id

    USER[user_id] = mode

    await q.message.reply_text(f"✅ {mode.upper()} MODE ACTIVE")

    steps = get_connector(mode)

    if steps:
        await q.message.reply_text(
            "🔗 NEXT STEPS:\n\n" + "\n".join("➡️ " + s for s in steps)
        )
    else:
        await q.message.reply_text("⚠️ Нет данных для режима")

# =========================
# MAIN
# =========================
def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    print("🔄 RUNNING ON RENDER...")

    app.run_polling()

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
