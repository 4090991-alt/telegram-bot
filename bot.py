import os
import logging
import uuid
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
TINKOFF_KEY = os.getenv("TINKOFF_TERMINAL_KEY")

logging.basicConfig(level=logging.INFO)

# =========================
# SIMPLE STATE
# =========================
USER_STATE = {}

# =========================
# TINKOFF PAYMENT (INLINE)
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
        "💼 Career SaaS V2\nВыберите услугу:",
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
    # SERVICES → PAYMENT
    # =========================
    if data in ["resume", "company", "jobs", "interview"]:

        USER_STATE[user_id] = data

        payment_url = create_payment(
            user_id=user_id,
            service=data,
            amount=10
        )

        await query.message.reply_text(
            f"""
💳 Услуга: {data}
💰 Цена: 10₽

👉 Оплатите по ссылке:
{payment_url}

После оплаты доступ будет открыт автоматически (V3 добавим webhook).
"""
        )
        return


# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
