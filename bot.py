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
# STATE LAYER (SAFE)
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
        "💼 CAREER ENGINE V6 (SAAS CONNECTOR)\n\nВыберите режим:",
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
        [InlineKeyboardButton("🤝 Интервью", callback_data="interview")]
    ]

    await q.message.reply_text(
        f"✅ MODE: {q.data.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE (SAFE SAAS CORE)
# =========================
def engine(mode, action):

    data = {
        "free": {
            "resume": "📄 FREE резюме (HH формат)",
            "company": "🏢 Базовый анализ компании",
            "jobs": "🔎 Базовые вакансии",
            "interview": "🤝 Базовые HR вопросы"
        },
        "pro": {
            "resume": "📄 PRO: опыт + достижения + усиление",
            "company": "🏢 PRO: зарплаты + риски + структура",
            "jobs": "🔎 PRO: сравнение вакансий + стратегия",
            "interview": "🤝 PRO: разбор ответов + улучшение"
        },
        "vip": {
            "resume": "📄 VIP: позиционирование кандидата",
            "company": "🏢 VIP: стратегия входа в компанию",
            "jobs": "🔎 VIP: карьерная стратегия",
            "interview": "🤝 VIP: симуляция интервью"
        }
    }

    return data.get(mode, data["free"]).get(action, "❌ нет данных")

# =========================
# CONNECTOR MAP (СВЯЗИ СХЕМЫ)
# =========================
def connector(action):

    return {
        "resume": [
            "➡️ PRO анализ компании",
            "➡️ вакансии под профиль",
            "➡️ HR симуляция"
        ],
        "company": [
            "➡️ улучшить резюме",
            "➡️ вакансии рынка",
            "➡️ VIP стратегия"
        ],
        "jobs": [
            "➡️ усилить резюме",
            "➡️ HR подготовка",
            "➡️ VIP стратегия входа"
        ],
        "interview": [
            "➡️ улучшить резюме",
            "➡️ вакансии",
            "➡️ VIP стратегия"
        ]
    }.get(action, [])

# =========================
# ACTION ROUTER (FIXED SAFE)
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query

    if not q:
        return

    await q.answer()

    user_id = q.from_user.id
    action = q.data
    mode = USER_MODE.get(user_id, "free")

    # INIT FLOW
    if action == "resume":
        USER_FLOW[user_id] = {"step": 1, "data": {}}
        await q.message.reply_text("📌 Введите ФИО:")
        return

    # SAFETY: always respond
    result = engine(mode, action)
    await q.message.reply_text(result)

    next_steps = connector(action)

    if next_steps:
        await q.message.reply_text(
            "🔗 СЛЕДУЮЩИЕ ШАГИ:\n" + "\n".join(next_steps)
        )

# =========================
# RESUME FLOW (NO DEAD ZONES)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]

    step = flow.get("step", 1)

    if step == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт работы:")
        return

    if step == 2:
        flow["data"]["exp"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование:")
        return

    if step == 3:
        flow["data"]["edu"] = text

        USER_FLOW[user_id] = {}

        await update.message.reply_text(
            "📄 ГОТОВО\n\n"
            "✔ данные собраны\n"
            "➡️ выбери следующий шаг: PRO / JOBS / INTERVIEW"
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
