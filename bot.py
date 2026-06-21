import os
import logging
import tempfile

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
        "💼 CAREER ENGINE V5.1\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE SELECTOR
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    mode = q.data

    USER_MODE[user_id] = mode

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Интервью", callback_data="interview")],
    ]

    await q.message.reply_text(
        f"✅ MODE: {mode.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE CORE (SAFE)
# =========================
def engine(mode, action):

    if mode == "free":
        return {
            "resume": "📄 FREE резюме (HH формат)",
            "company": "🏢 Базовый анализ компании",
            "jobs": "🔎 Базовые вакансии",
            "interview": "🤝 Базовые HR вопросы",
        }.get(action, "❌ неизвестно")

    if mode == "pro":
        return {
            "resume": "📄 PRO: опыт + достижения + усиление",
            "company": "🏢 PRO: зарплаты + риски + структура",
            "jobs": "🔎 PRO: сравнение вакансий + стратегия",
            "interview": "🤝 PRO: разбор ответов + улучшение",
        }.get(action, "❌ неизвестно")

    return {
        "resume": "📄 VIP: позиционирование кандидата",
        "company": "🏢 VIP: стратегия входа",
        "jobs": "🔎 VIP: карьерная стратегия",
        "interview": "🤝 VIP: симуляция интервью",
    }.get(action, "❌ неизвестно")

# =========================
# CONNECTOR (СВЯЗИ КАРТЫ)
# =========================
def connector(action):

    return {
        "resume": [
            "➡️ PRO анализ компании",
            "➡️ вакансии под резюме",
            "➡️ HR симуляция"
        ],
        "company": [
            "➡️ улучшить резюме под рынок",
            "➡️ вакансии этой сферы",
            "➡️ VIP стратегия"
        ],
        "jobs": [
            "➡️ усилить резюме (PRO)",
            "➡️ HR подготовка",
            "➡️ VIP стратегия входа"
        ],
        "interview": [
            "➡️ усилить резюме",
            "➡️ вакансии",
            "➡️ VIP стратегия"
        ]
    }.get(action, [])

# =========================
# ACTION ROUTER (FIXED)
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.callback_query:
        return

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    action = q.data
    mode = USER_MODE.get(user_id, "free")

    if action == "resume":
        USER_FLOW[user_id] = {"step": 1, "data": {}}
        await q.message.reply_text("📌 Введите ФИО:")
        return

    result = engine(mode, action)
    await q.message.reply_text(result)

    next_steps = connector(action)
    if next_steps:
        await q.message.reply_text(
            "🔗 СЛЕДУЮЩИЕ ШАГИ:\n" + "\n".join(next_steps)
        )

# =========================
# RESUME FLOW (STABLE)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]

    if flow["step"] == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт работы:")
        return

    if flow["step"] == 2:
        flow["data"]["exp"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование:")
        return

    if flow["step"] == 3:
        flow["data"]["edu"] = text

        USER_FLOW[user_id] = {}

        await update.message.reply_text(
            "📄 ГОТОВО\n\n"
            "✔ данные собраны\n"
            "➡️ выбери следующий шаг"
        )

# =========================
# RUN
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(action_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    app.run_polling()

if __name__ == "__main__":
    main()
