import os
import io
import logging
from datetime import datetime

from flask import Flask, jsonify
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

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise Exception("Missing keys")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# WEB DASHBOARD
# =========================
app_web = Flask(__name__)

# =========================
# CRM CORE
# =========================
users = {}
subscriptions = set()
revenue = 0

FREE_LIMIT = 5

# =========================
# STATE MACHINE
# =========================
state = {}

def get_state(uid):
    if uid not in state:
        state[uid] = {
            "stage": "menu",
            "product": None,
            "data": {},
            "paid": False
        }
    return state[uid]

# =========================
# ACCESS CONTROL
# =========================
def allowed(uid):
    return uid in subscriptions or users.get(uid, {}).get("usage", 0) < FREE_LIMIT

def track(uid):
    if uid not in users:
        users[uid] = {"usage": 0, "created": datetime.now()}
    users[uid]["usage"] += 1

# =========================
# START MENU
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_state(uid)

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование", callback_data="interview")]
    ]

    await update.message.reply_text(
        "👋 Career AI System\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# FLOW CONTROLLER
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    st = get_state(uid)

    # PAYMENT CONFIRM
    if q.data == "paid":
        subscriptions.add(uid)
        st["paid"] = True
        await q.message.reply_text("✅ PRO доступ активирован")
        return

    st["product"] = q.data
    st["stage"] = "collecting"

    if q.data == "resume":
        msg = "📄 Введите: ФИО, опыт, должность"
        price = "FREE → PRO → VIP"

    elif q.data == "company":
        msg = "🏢 Введите: компания + город"
        price = "FREE preview → PAID analysis"

    else:
        msg = "🎤 Подготовка к интервью (описание опыта)"
        price = "Paid module"

    keyboard = [[InlineKeyboardButton("💳 Активировать PRO", callback_data="paid")]]

    await q.message.reply_text(
        f"{msg}\n\n💰 Модель: {price}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# AI ENGINE (CONTROLLED)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    track(uid)

    if not allowed(uid):
        await update.message.reply_text("Лимит исчерпан. /start")
        return

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты карьерный HR AI. Давай структурированные, краткие, полезные ответы."
                },
                {"role": "user", "content": text}
            ]
        )

        await update.message.reply_text(
            response.choices[0].message.content[:3500]
        )

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Ошибка системы")

# =========================
# PDF GENERATOR (RESUME)
# =========================
def generate_pdf(text):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, "CAREER CV")
    p.drawString(100, 750, text[:200])
    p.save()
    buffer.seek(0)
    return buffer

# =========================
# ADMIN PANEL (WEB)
# =========================
@app_web.route("/admin")
def admin():
    return jsonify({
        "users": len(users),
        "subscriptions": len(subscriptions),
        "revenue": revenue
    })

# =========================
# BOT INIT
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

# =========================
# RUN (BOT + WEB)
# =========================
if __name__ == "__main__":
    import threading

    threading.Thread(target=lambda: app_web.run(host="0.0.0.0", port=8080)).start()
    app.run_polling()
