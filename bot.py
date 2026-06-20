import os
import logging
import uuid
import requests
import psycopg2

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TINKOFF_KEY = os.getenv("TINKOFF_TERMINAL_KEY")

USER_STATE = {}

# =========================
# DB CHECK ACCESS
# =========================
def check_access(user_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("SELECT status FROM users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()

        conn.close()

        return row and row[0] == "PAID"
    except:
        return False


# =========================
# PAYMENT
# =========================
def create_payment(user_id, service, amount=10):

    url = "https://securepay.tinkoff.ru/v2/Init"
    order_id = str(uuid.uuid4())

    payload = {
        "TerminalKey": TINKOFF_KEY,
        "Amount": amount * 100,
        "OrderId": order_id,
        "Description": service,
        "DATA": {
            "user_id": str(user_id),
            "service": service
        }
    }

    r = requests.post(url, json=payload)
    data = r.json()

    return data.get("PaymentURL")


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Собеседование", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 SaaS V3 SYSTEM",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# CALLBACK
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # =========================
    # ACCESS CHECK (ВАЖНО)
    # =========================
    if not check_access(user_id):
        payment_url = create_payment(user_id, data, 10)

        await query.message.reply_text(
            f"⛔ Доступ не активирован\n\n💳 Оплата:\n{payment_url}"
        )
        return

    # =========================
    # SERVICES (ПОСЛЕ ОПЛАТЫ)
    # =========================
    if data == "resume":
        text = "📄 Отправьте: ФИО, опыт, образование"

    elif data == "company":
        text = "🏢 Отправьте: компания + город"

    elif data == "jobs":
        text = "🔎 Отправьте: должность + город"

    elif data == "interview":
        text = "🤝 Подготовка к собеседованию активна"

    else:
        text = "Ошибка"

    await query.message.reply_text(text)


# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
