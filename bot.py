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
# STATE LAYER (SAFE)
# =========================
USER_MODE = {}
USER_FLOW = {}

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
        "💼 CAREER ENGINE V4.2\n\nВыберите режим:",
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

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Собеседование", callback_data="interview")]
    ]

    await query.message.reply_text(
        f"✅ Режим: {mode.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE CORE (SAFE)
# =========================
def company_engine(mode):
    return {
        "free": "🏢 Базовый анализ",
        "pro": "🏢 Зарплаты + риски + отзывы",
        "vip": "🏢 Стратегия трудоустройства"
    }.get(mode, "free")

def jobs_engine(mode):
    return {
        "free": "🔎 Базовые вакансии",
        "pro": "🔎 Сравнение + расширенный подбор",
        "vip": "🔎 Карьерная стратегия"
    }.get(mode, "free")

def interview_engine(mode):
    return {
        "free": "🤝 Базовые HR вопросы",
        "pro": "🤝 Разбор ответов",
        "vip": "🤝 Симуляция интервью"
    }.get(mode, "free")

# =========================
# PDF ENGINE (STABLE PRO)
# =========================
def generate_pdf(data, mode):

    file_path = tempfile.mktemp(suffix=".pdf")
    c = canvas.Canvas(file_path, pagesize=A4)

    y = 800

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, y, f"RESUME - {mode.upper()} MODE")
    y -= 40

    # FIO
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "ФИО:")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(120, y, data.get("fio", ""))
    y -= 40

    # EXPERIENCE
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "ОПЫТ:")
    y -= 20

    c.setFont("Helvetica", 10)
    for line in str(data.get("experience", "")).split("\n"):
        if line.strip():
            c.drawString(120, y, f"• {line}")
            y -= 18

    y -= 20

    # EDUCATION
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "ОБРАЗОВАНИЕ:")
    y -= 20

    c.setFont("Helvetica", 10)
    for line in str(data.get("education", "")).split("\n"):
        if line.strip():
            c.drawString(120, y, f"• {line}")
            y -= 18

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(100, 50, "AI Career Engine V4.2")

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

    # SAFE INIT FLOW
    if action == "resume":
        USER_FLOW[user_id] = {"step": 1, "data": {}}
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

    await query.message.reply_text("❌ Ошибка")

# =========================
# RESUME FLOW (ROBUST + SAFE)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]
    mode = USER_MODE.get(user_id, "free")

    # STEP 1
    if flow["step"] == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт работы:")
        return

    # STEP 2
    if flow["step"] == 2:
        flow["data"]["experience"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование и навыки:")
        return

    # STEP 3 → FINAL PDF
    if flow["step"] == 3:
        flow["data"]["education"] = text

        pdf_file = generate_pdf(flow["data"], mode)

        USER_FLOW[user_id] = {}

        with open(pdf_file, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="resume.pdf",
                caption=f"📄 Резюме готово ({mode.upper()})"
            )

# =========================
# APP
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(action_handler, pattern="^(resume|company|jobs|interview)$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    app.run_polling()

if __name__ == "__main__":
    main()
