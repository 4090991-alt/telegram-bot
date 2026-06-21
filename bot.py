import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# =========================
# STATE
# =========================
USER_MODE = {}
USER_FLOW = {}

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🟢 FREE", callback_data="free")],
        [InlineKeyboardButton("🟡 PRO", callback_data="pro")],
        [InlineKeyboardButton("🔴 VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "💼 CAREER ENGINE V6 (SAAS ARCHITECTURE)\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE SELECTOR
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    USER_MODE[q.from_user.id] = q.data

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 HR", callback_data="interview")],
        [InlineKeyboardButton("🌐 Сайт", callback_data="site")]
    ]

    await q.message.reply_text(
        f"✅ MODE: {q.data.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE
# =========================
def engine(mode, action):

    if mode == "free":
        return {
            "resume": "📄 FREE резюме",
            "company": "🏢 базовый анализ",
            "jobs": "🔎 базовые вакансии",
            "interview": "🤝 HR вопросы",
            "site": "🌐 простая визитка"
        }.get(action)

    if mode == "pro":
        return {
            "resume": "📄 PRO резюме (усиление)",
            "company": "🏢 зарплаты + риски + рынок",
            "jobs": "🔎 сравнение вакансий",
            "interview": "🤝 разбор ответов",
            "site": "🌐 PRO структура сайта"
        }.get(action)

    return {
        "resume": "📄 VIP позиционирование",
        "company": "🏢 стратегия входа",
        "jobs": "🔎 карьерная стратегия",
        "interview": "🤝 симуляция интервью",
        "site": "🌐 VIP лендинг"
    }.get(action)

# =========================
# CONNECTOR (КАРТА СВЯЗЕЙ)
# =========================
def connector(action):

    return {
        "resume": ["PRO анализ", "вакансии", "HR", "сайт"],
        "company": ["резюме", "вакансии", "VIP стратегия"],
        "jobs": ["резюме", "HR", "VIP стратегия"],
        "interview": ["резюме", "вакансии", "VIP"],
        "site": ["резюме", "PRO анализ", "вакансии"]
    }.get(action, [])

# =========================
# ACTION ROUTER
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.callback_query:
        return

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    action = q.data
    mode = USER_MODE.get(user_id, "free")

    result = engine(mode, action)

    await q.message.reply_text(result)

    next_steps = connector(action)

    if next_steps:
        await q.message.reply_text(
            "🔗 СЛЕДУЮЩИЕ ШАГИ:\n" + "\n".join(next_steps)
        )

# =========================
# FLOW (RESUME MINIMAL SAFE)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]

    if flow["step"] == 1:
        flow["step"] = 2
        flow["data"] = {"fio": text}
        await update.message.reply_text("Опыт:")
        return

    if flow["step"] == 2:
        flow["step"] = 3
        flow["data"]["exp"] = text
        await update.message.reply_text("Образование:")
        return

    if flow["step"] == 3:
        flow["data"]["edu"] = text
        USER_FLOW[user_id] = {}

        await update.message.reply_text(
            "✔ готово\n➡️ выбери следующий шаг из системы"
        )

# =========================
# RUN
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    app.run_polling()

if __name__ == "__main__":
    main()
