import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ NO TOKEN FOUND")
    raise SystemExit()

logging.basicConfig(level=logging.INFO)

print("BOT STARTED OK")

USER = {}

# =========================
# RESUME MODULE STORAGE
# =========================
USER_STATE = {}
USER_DATA = {}

# =========================
# MENU DATA
# =========================
def get_connector(mode):
    return {
        "free": ["РЕЗЮМЕ", "Вакансии", "HR интервью"],
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
        [InlineKeyboardButton("VIP", callback_data="vip")],
        [InlineKeyboardButton("📄 РЕЗЮМЕ", callback_data="resume")]
    ]

    await update.message.reply_text(
        "🚀 CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK HANDLER
# =========================
async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id

    # режимы
    if q.data in ["free", "pro", "vip"]:
        USER[user_id] = q.data
        await q.message.reply_text(f"✅ {q.data.upper()} MODE ACTIVE")

        for step in get_connector(q.data):
            await q.message.reply_text("➡️ " + step)

    # запуск резюме
    elif q.data == "resume":
        USER_STATE[user_id] = "resume_name"
        USER_DATA[user_id] = {}
        await q.message.reply_text("📄 Введите ваше ФИО:")

# =========================
# RESUME FLOW (диалог)
# =========================
async def resume_flow(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in USER_STATE:
        return

    state = USER_STATE[user_id]

    if state == "resume_name":
        USER_DATA[user_id]["name"] = text
        USER_STATE[user_id] = "resume_exp"
        await update.message.reply_text("💼 Опыт работы (кратко):")

    elif state == "resume_exp":
        USER_DATA[user_id]["exp"] = text
        USER_STATE[user_id] = "resume_skills"
        await update.message.reply_text("🧠 Навыки:")

    elif state == "resume_skills":
        USER_DATA[user_id]["skills"] = text

        data = USER_DATA[user_id]

        resume = f"""
📄 РЕЗЮМЕ

👤 ФИО: {data['name']}

💼 Опыт:
{data['exp']}

🧠 Навыки:
{data['skills']}

━━━━━━━━━━━━━━
AI CAREER BOT
"""

        await update.message.reply_text(resume)

        del USER_STATE[user_id]
        del USER_DATA[user_id]

# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))

    # важно: обработка текста для резюме
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    print("RUNNING...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )

if __name__ == "__main__":
    main()
