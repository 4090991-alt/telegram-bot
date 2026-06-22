import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ NO TOKEN FOUND")
    raise SystemExit()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print("🚀 BOT STARTED OK")

# =========================
# MEMORY
# =========================
USER = {}

# =========================
# DATA
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

# =========================
# CALLBACK
# =========================
async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()

    mode = q.data
    USER[q.from_user.id] = mode

    await q.message.reply_text(f"✅ {mode.upper()} MODE ACTIVE")

    steps = get_connector(mode)

    for step in steps:
        await q.message.reply_text("➡️ " + step)

# =========================
# MAIN (STABLE RENDER FIX)
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    # 🔥 КЛЮЧЕВОЙ FIX: убираем старые webhook/updates конфликты
    app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    print("RUNNING...")

    # 🔥 Render-safe polling
    app.run_polling(
        drop_pending_updates=True
    )

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
