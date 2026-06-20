import os
import io
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from openai import OpenAI
from reportlab.pdfgen import canvas

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# KEYS
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# STORAGE (MVP CRM)
# =========================
state = {}
users = {}
subscriptions = set()
revenue = 0

FREE_LIMIT = 5

# =========================
# STATE MACHINE
# =========================
def get_state(user_id):
    if user_id not in state:
        state[user_id] = {
            "stage": "menu",
            "product": None,
            "plan": None,
            "data": {},
            "photo": None,
            "paid": False
        }
    return state[user_id]

# =========================
# CRM
# =========================
def track(user_id):
    if user_id not in users:
        users[user_id] = {"usage": 0, "created": datetime.now()}
    users[user_id]["usage"] += 1

def allowed(user_id):
    return user_id in subscriptions or users.get(user_id, {}).get("usage", 0) < FREE_LIMIT

# =========================
# START MENU
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_state(uid)

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование", callback_data="interview")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")]
    ]

    await update.message.reply_text(
        "👋 Career AI System",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# PHOTO ENGINE (1 PHOTO ONLY)
# =========================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_state(uid)

    # ❌ уже есть фото
    if st["photo"]:
        await update.message.reply_text("📌 Можно загрузить только 1 фото")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    os.makedirs("photos", exist_ok=True)
    path = f"photos/{uid}.jpg"

    await file.download_to_drive(path)

    st["photo"] = path

    await update.message.reply_text("✅ Фото добавлено в резюме")

# =========================
# FLOW CONTROLLER
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_state(uid)

    # PAYMENT
    if q.data == "paid":
        subscriptions.add(uid)
        st["paid"] = True
        await q.message.reply_text("✅ PRO доступ активирован")
        return

    # PRODUCT SELECT
    st["product"] = q.data
    st["stage"] = "plan_select"

    if q.data == "resume":
        text = "📄 Выберите тип резюме"
        keyboard = [
            [InlineKeyboardButton("🟢 FREE", callback_data="resume_free")],
            [InlineKeyboardButton("🟡 PRO", callback_data="resume_pro")],
            [InlineKeyboardButton("🔴 VIP", callback_data="resume_vip")]
        ]

    elif q.data == "company":
        text = "🏢 Анализ компании (введите: компания + город)"
        keyboard = []

    elif q.data == "interview":
        text = "🎤 Интервью (платные модули)"
        keyboard = []

    else:
        text = "🔎 Введите город и должность"
        keyboard = []

    kb = InlineKeyboardMarkup(keyboard) if keyboard else None

    await q.message.reply_text(text, reply_markup=kb)

# =========================
# TEXT FLOW (MAIN LOGIC)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    st = get_state(uid)

    track(uid)

    if not allowed(uid):
        await update.message.reply_text("❌ Лимит исчерпан")
        return

    # =========================
    # RESUME FREE
    # =========================
    if st["product"] == "resume":
        if st["plan"] is None:
            await update.message.reply_text("Выберите тариф через /start")
            return

        if st["plan"] == "free":
            st["data"]["raw"] = text

            pdf = generate_pdf(text, st.get("photo"))

            await update.message.reply_document(pdf, filename="resume.pdf")

            await update.message.reply_text(
                "Хотите PRO или VIP версию?"
            )

        elif st["plan"] == "pro":
            st["data"]["pro"] = text
            pdf = generate_pdf("PRO RESUME:\n" + text, st.get("photo"))

            await update.message.reply_document(pdf, filename="pro_resume.pdf")

        elif st["plan"] == "vip":
            st["data"]["vip"] = text
            pdf = generate_pdf("VIP CAREER STRATEGY:\n" + text, st.get("photo"))

            await update.message.reply_document(pdf, filename="vip_resume.pdf")

        return

    # =========================
    # COMPANY ANALYSIS
    # =========================
    if st["product"] == "company":
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "HR analyst. Give structured company analysis."},
                {"role": "user", "content": text}
            ]
        )

        await update.message.reply_text(response.choices[0].message.content)
        return

    # =========================
    # DEFAULT AI
    # =========================
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Career AI assistant"},
            {"role": "user", "content": text}
        ]
    )

    await update.message.reply_text(response.choices[0].message.content)

# =========================
# PDF ENGINE (WITH PHOTO)
# =========================
def generate_pdf(text, photo_path=None):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(100, 800, "CAREER RESUME")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 770, text[:200])

    if photo_path:
        try:
            pdf.drawImage(photo_path, 400, 700, width=120, height=150)
        except:
            pass

    pdf.save()
    buffer.seek(0)
    return buffer

# =========================
# APP INIT
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run_polling()
