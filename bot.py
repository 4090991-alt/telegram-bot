import os
import logging
import psycopg2
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
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# DB
# =========================
def db_conn():
    return psycopg2.connect(DATABASE_URL)

def save_user(user_id, mode):
    try:
        conn = db_conn()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            mode TEXT,
            score INT DEFAULT 0
        )
        """)

        cur.execute("""
        INSERT INTO users (user_id, mode)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET mode = EXCLUDED.mode
        """, (user_id, mode))

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(e)

def update_score(user_id, score):
    try:
        conn = db_conn()
        cur = conn.cursor()

        cur.execute("""
        UPDATE users SET score=%s WHERE user_id=%s
        """, (score, user_id))

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(e)

# =========================
# AI
# =========================
def scoring_engine(text):
    score = 50
    if "опыт" in text.lower():
        score += 10
    if "достижения" in text.lower():
        score += 15
    if "20" in text:
        score += 10
    return min(score, 100)

def ai_resume_generator(data):
    return f"""
ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ

ФИО:
{data.get('fio')}

ОПЫТ:
{data.get('exp')}

ОБРАЗОВАНИЕ:
{data.get('edu')}
"""

# =========================
# PDF ENGINE (FIX)
# =========================
def generate_pdf(data):

    file_path = tempfile.mktemp(suffix=".pdf")
    c = canvas.Canvas(file_path, pagesize=A4)

    y = 800

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, y, "AI RESUME - CAREER ENGINE V7")
    y -= 40

    c.setFont("Helvetica", 12)

    for key in ["fio", "exp", "edu"]:
        c.drawString(100, y, f"{key.upper()}:")
        y -= 20
        c.drawString(120, y, str(data.get(key, "")))
        y -= 40

    c.save()
    return file_path

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
        "🚀 CAREER ENGINE V7 PRODUCTION\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    USER_MODE[q.from_user.id] = q.data
    save_user(q.from_user.id, q.data)

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Интервью", callback_data="interview")]
    ]

    await q.message.reply_text(
        f"✅ MODE: {q.data.upper()}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ROUTER
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    action = q.data

    if action == "resume":
        USER_FLOW[user_id] = {"step": 1, "data": {}}
        await q.message.reply_text("📌 Введите ФИО:")
        return

    await q.message.reply_text("⚙️ функция в разработке")

# =========================
# FLOW + PDF FIX
# =========================
async def flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]

    if flow["step"] == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт:")
        return

    if flow["step"] == 2:
        flow["data"]["exp"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование:")
        return

    if flow["step"] == 3:
        flow["data"]["edu"] = text

        score = scoring_engine(text)
        update_score(user_id, score)

        pdf_file = generate_pdf(flow["data"])

        USER_FLOW[user_id] = {}

        await update.message.reply_document(
            document=open(pdf_file, "rb"),
            filename="resume.pdf",
            caption=f"📄 Резюме готово | SCORE: {score}/100"
        )

# =========================
# APP
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, flow))

    app.run_polling()

if __name__ == "__main__":
    main()
