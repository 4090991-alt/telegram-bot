import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# =========================
# STATE
# =========================
USER_MODE = {}

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

    text = f"✅ Режим выбран: {mode.upper()}\n\nВыберите действие:"

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
    if mode == "free":
        return "📄 FREE резюме (HH формат)\n👉 ФИО + опыт + образование"
    if mode == "pro":
        return "📄 PRO резюме\n👉 Опыт по годам + навыки + достижения"
    return "📄 VIP резюме\n👉 Под вакансию + стратегия + усиление"


def company_engine(mode):
    if mode == "free":
        return "🏢 Базовый анализ компании"
    if mode == "pro":
        return "🏢 Расширенный анализ (зарплаты, риски, отзывы)"
    return "🏢 Глубокий анализ + стратегия входа"


def jobs_engine(mode):
    if mode == "free":
        return "🔎 Базовые вакансии (ссылки)"
    if mode == "pro":
        return "🔎 Расширенный подбор + сравнение вакансий"
    return "🔎 Вакансии + стратегия выбора работодателя"


def interview_engine(mode):
    if mode == "free":
        return "🤝 Базовые HR вопросы"
    if mode == "pro":
        return "🤝 HR + разбор ответов"
    return "🤝 Полная симуляция интервью + стресс тест"


# =========================
# ACTION HANDLER
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data
    mode = USER_MODE.get(user_id, "free")

    if action == "resume":
        text = resume_engine(mode)

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
# APP START (ВАЖНО FIX RAILWAY)
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$")
    )

    app.add_handler(CallbackQueryHandler(action_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
