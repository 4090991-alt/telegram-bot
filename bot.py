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
# STATE MACHINE (FIXED)
# =========================
state = {}
users = {}
subscriptions = set()

FREE_LIMIT = 5

def get_state(uid):
    if uid not in state:
        state[uid] = {
            "stage": "menu",          # menu → plan → collect → done
            "product": None,
            "plan": None,
            "data": {},
            "photo": None,
            "locked": False
        }
    return state[uid]

# =========================
# CRM
# =========================
def track(uid):
    if uid not in users:
        users[uid] = {"usage": 0}
    users[uid]["usage"] += 1

def allowed(uid):
    return uid in subscriptions or users.get(uid, {}).get("usage", 0) < FREE_LIMIT

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_state(uid)
    st["stage"] = "menu"

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование", callback_data="interview")],
    ]

    await update.message.reply_text(
        "👋 Career AI System",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# PHOTO ENGINE (1 PHOTO ONLY FIXED)
# =========================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_state(uid)

    # ❌ блок если уже есть фото
    if st["photo"]:
        await update.message.reply_text("📌 Можно загрузить только 1 фото")
        return

    if st["stage"] not in ["collect", "plan"]:
        await update.message.reply_text("📌 Сначала выберите резюме")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    os.makedirs("photos", exist_ok=True)
    path = f"photos/{uid}.jpg"

    await file.download_to_drive(path)

    st["photo"] = path

    await update.message.reply_text("✅ Фото добавлено")

# =========================
# BUTTON FLOW (FIXED STATE)
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_state(uid)

    # -------------------------
    # PAYMENT
    # -------------------------
    if q.data == "paid":
        subscriptions.add(uid)
        st["locked"] = True
        await q.message.reply_text("✅ PRO/VIP активирован")
        return

    # -------------------------
    # PRODUCT SELECT
    # -------------------------
    st["product"] = q.data
    st["stage"] = "plan"

    if q.data == "resume":
        keyboard = [
            [InlineKeyboardButton("🟢 FREE", callback_data="resume_free")],
            [InlineKeyboardButton("🟡 PRO", callback_data="resume_pro")],
            [InlineKeyboardButton("🔴 VIP", callback_data="resume_vip")]
        ]

        text = "📄 Выберите тип резюме"

    elif q.data == "company":
        text = "🏢 Введите: компания + город"
        keyboard = []

    else:
        text = "🎤 Подготовка к интервью"
        keyboard = []

    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

    # -------------------------
    # PLAN SAVE FIX
    # -------------------------
    if q.data.startswith("resume_"):
        st["plan"] = q.data.replace("resume_", "")
        st["stage"] = "collect"

        if st["plan"] == "free":
            await q.message.reply_text("📄 Введите: ФИО, опыт, должность")

        if st["plan"] == "pro":
            await q.message.reply_text("📄 Введите опыт ПО ГОДАМ, достижения, должности")

        if st["plan"] == "vip":
            await q.message.reply_text("📄 Введите полный карьерный путь + цели + достижения")

# =========================
# CHAT ENGINE (HARD LOCKED FLOW)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    st = get_state(uid)

    track(uid)

    # ❌ HARD LOCK
    if st["stage"] not in ["collect"]:
        await update.message.reply_text("📌 Сначала выберите услугу через /start")
        return

    if not allowed(uid):
        await update.message.reply_text("❌ Лимит исчерпан")
        return

    st["data"]["input"] = text

    # =========================
    # RESUME OUTPUT (SINGLE OUTPUT FIX)
    # =========================
    if st["product"] == "resume":

        pdf = generate_pdf(text, st.get("photo"))

        st["stage"] = "done"

        await update.message.reply_document(pdf, filename="resume.pdf")

        await update.message.reply_text(
            "⬇️ Хотите усиление?\nPRO / VIP доступны в меню"
        )
        return

    # =========================
    # COMPANY
    # =========================
    if st["product"] == "company":

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты HR аналитик. Дай структурированный анализ компании."},
                {"role": "user", "content": text}
            ]
        )

        st["stage"] = "done"

        await update.message.reply_text(response.choices[0].message.content)
        return

# =========================
# PDF ENGINE (WITH PHOTO FIX)
# =========================
def generate_pdf(text, photo=None):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(100, 800, "RESUME")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 770, text[:200])

    if photo:
        try:
            pdf.drawImage(photo, 400, 700, width=120, height=150)
        except:
            pass

    pdf.save()
    buffer.seek(0)
    return buffer

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

if __name__ == "__main__":
    app.run_polling()
