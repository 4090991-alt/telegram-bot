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
USER_RESUME = {}

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🟢 FREE режим", callback_data="free")],
        [InlineKeyboardButton("🟡 PRO режим", callback_data="pro")],
        [InlineKeyboardButton("🔴 VIP режим", callback_data="vip")]
    ]

    await update.message.reply_text(
        "💼 CAREER ENGINE V1\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE SELECTOR
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    mode = query.data

    USER_MODE[user_id] = mode

    text = f"✅ Режим: {mode.upper()}\n\nВыберите действие:"

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Собеседование", callback_data="interview")]
    ]

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE CORE
# =========================
def resume_engine(mode):
    return {
        "free": "📄 FREE резюме (HH формат)\n👉 ФИО + опыт + образование",
        "pro": "📄 PRO резюме\n👉 Опыт по годам + навыки + достижения",
        "vip": "📄 VIP резюме\n👉 Под вакансию + стратегия + усиление"
    }[mode]

def company_engine(mode):
    return {
        "free": "🏢 Базовый анализ компании",
        "pro": "🏢 Расширенный анализ (зарплаты, риски, отзывы)",
        "vip": "🏢 Глубокий анализ + стратегия входа"
    }[mode]

def jobs_engine(mode):
    return {
        "free": "🔎 Базовые вакансии (ссылки)",
        "pro": "🔎 Расширенный подбор + сравнение вакансий",
        "vip": "🔎 Вакансии + стратегия выбора работодателя"
    }[mode]

def interview_engine(mode):
    return {
        "free": "🤝 Базовые HR вопросы",
        "pro": "🤝 HR + разбор ответов",
        "vip": "🤝 Полная симуляция интервью + стресс тест"
    }[mode]

# =========================
# ACTION HANDLER
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data
    mode = USER_MODE.get(user_id, "free")

    # 🚀 RESUME V2 START FLOW
    if action == "resume":
        USER_RESUME[user_id] = {"step": 1, "data": {}}
        await query.message.reply_text("📌 Введите ФИО и должность:")
        return

    elif action == "company":
        text = company_engine(mode)

    elif action == "jobs":
        text = jobs_engine(mode)

    elif action == "interview":
        text = interview_engine(mode)

    else:
        text = "Ошибка действия"

    await query.message.reply_text(text)

# =========================
# RESUME FLOW V2 (HR ENGINE)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_RESUME:
        return

    state = USER_RESUME[user_id]
    mode = USER_MODE.get(user_id, "free")

    if state["step"] == 1:
        state["data"]["main"] = text
        state["step"] = 2
        await update.message.reply_text("📌 Введите опыт работы (по годам):")
        return

    if state["step"] == 2:
        state["data"]["experience"] = text
        state["step"] = 3
        await update.message.reply_text("📌 Введите образование и навыки:")
        return

    if state["step"] == 3:
        state["data"]["education"] = text

        result = f"""
📄 ГОТОВОЕ РЕЗЮМЕ

👤 {state['data']['main']}

💼 ОПЫТ:
{state['data']['experience']}

🎓 ОБРАЗОВАНИЕ / НАВЫКИ:
{state['data']['education']}

---
✔ Формат: HeadHunter
✔ Режим: {mode.upper()}
"""

        USER_RESUME[user_id] = {}

        await update.message.reply_text(result)

# =========================
# APP
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$")
    )

    app.add_handler(
        CallbackQueryHandler(action_handler, pattern="^(resume|company|jobs|interview)$")
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow)
    )

    app.run_polling()

if __name__ == "__main__":
    main()
