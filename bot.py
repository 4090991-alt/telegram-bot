import os
import logging
import tempfile

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

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
        "💼 CAREER ENGINE V3\n\nВыберите режим:",
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
def company_engine(mode):
    return {
        "free": "🏢 Базовый анализ компании",
        "pro": "🏢 Расширенный анализ (зарплаты, риски, отзывы)",
        "vip": "🏢 Глубокий анализ + стратегия входа"
    }.get(mode, "free")

def jobs_engine(mode):
    return {
        "free": "🔎 Базовые вакансии (ссылки)",
        "pro": "🔎 Расширенный подбор + сравнение вакансий",
        "vip": "🔎 Вакансии + стратегия выбора"
    }.get(mode, "free")

def interview_engine(mode):
    return {
        "free": "🤝 Базовые HR вопросы",
        "pro": "🤝 HR + разбор ответов",
        "vip": "🤝 Полная симуляция интервью"
    }.get(mode, "free")

# =========================
# PDF GENERATOR (STABLE)
# =========================
def generate_pdf(data):

    file_path = tempfile.mktemp(suffix=".pdf")

    c = canvas.Canvas(file_path, pagesize=A4)

    y = 800

    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y, "RESUME - CAREER ENGINE")
    y -= 40

    c.setFont("Helvetica", 11)

    for key, value in data.items():
        c.drawString(100, y, f"{key}: {value}")
        y -= 25

    c.save()

    return file_path

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
        USER_RESUME[user_id] = {"step": 1, "data": {}}
        await query.message.reply_text("📌 Введите ФИО и должность:")
        return

    if action == "company":
        await query.message.reply_text(company_engine(mode))
        return

    if action == "jobs":
        await query.message.reply_text(jobs_engine(mode))
        return

    if action == "interview":
        await query.message.reply_text(interview_engine(mode))
        return

    await query.message.reply_text("❌ Неизвестное действие")

# =========================
# RESUME FLOW + PDF
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_RESUME:
        return

    state = USER_RESUME[user_id]

    if state["step"] == 1:
        state["data"]["ФИО"] = text
        state["step"] = 2
        await update.message.reply_text("📌 Опыт работы (по годам):")
        return

    if state["step"] == 2:
        state["data"]["Опыт"] = text
        state["step"] = 3
        await update.message.reply_text("📌 Образование и навыки:")
        return

    if state["step"] == 3:
        state["data"]["Образование"] = text

        pdf_file = generate_pdf(state["data"])

        USER_RESUME[user_id] = {}

        with open(pdf_file, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="resume.pdf",
                caption="📄 Ваше резюме готово (PDF)"
            )

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
