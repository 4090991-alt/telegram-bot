import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ TOKEN NOT FOUND")
    raise SystemExit()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print("🚀 BOT FILE LOADED OK")

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
# START
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

    query = update.callback_query
    await query.answer()

    mode = query.data
    user_id = query.from_user.id

    USER[user_id] = mode

    await query.message.reply_text(f"✅ {mode.upper()} MODE ACTIVE")

    steps = get_connector(mode)

    if steps:
        await query.message.reply_text(
            "🔗 NEXT STEPS:\n\n" + "\n".join("➡️ " + s for s in steps)
        )
    else:
        await query.message.reply_text("⚠️ Нет данных")

# =========================
# MAIN (ВАЖНО ДЛЯ RENDER)
# =========================
def main():

    print("🔄 STARTING BOT...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    # 🔥 ВАЖНО: Render стабильнее с этим вариантом
    app.run_polling(drop_pending_updates=True)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
