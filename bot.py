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
logging.basicConfig(level=logging.INFO)
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

    for step in get_connector(mode):
        await q.message.reply_text("➡️ " + step)

# =========================
# MAIN (ЖЁСТКИЙ FIX RENDER)
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    # 🔥 КЛЮЧЕВОЙ FIX (ВАЖНО!)
    try:
        app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print("Webhook cleanup:", e)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    print("RUNNING...")

    # 🔥 СТАБИЛЬНЫЙ RUN
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
