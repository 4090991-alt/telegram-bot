import os
import logging
import uuid
import base64
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CLOUD_PUBLIC_ID = os.getenv("CLOUD_PUBLIC_ID")
CLOUD_API_SECRET = os.getenv("CLOUD_API_SECRET")

# =========================
# STATE (простое хранение)
# =========================
USER_STATE = {}

# =========================
# PAYMENT (CloudPayments ONLY)
# =========================
def create_payment(user_id, service, amount=10):

    auth = base64.b64encode(
        f"{CLOUD_PUBLIC_ID}:{CLOUD_API_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }

    payload = {
        "Amount": amount,
        "Currency": "RUB",
        "Description": service,
        "InvoiceId": str(uuid.uuid4()),
        "JsonData": {
            "user_id": user_id,
            "service": service
        }
    }

    r = requests.post(
        "https://api.cloudpayments.ru/payments/charges",
        json=payload,
        headers=headers
    )

    data = r.json()
    return data.get("Model", {}).get("Url")


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Помощь в собеседовании", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 Career System STABLE V1",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# HANDLER
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # сохраняем выбор
    USER_STATE[user_id] = data

    # =========================
    # PAYMENT FLOW
    # =========================
    payment_url = create_payment(user_id, data, 10)

    await query.message.reply_text(
        f"""
💳 Услуга: {data}
💰 Цена: 10₽

👉 Оплатите по ссылке:
{payment_url}

После оплаты доступ будет открыт (следующий этап V3).
"""
    )


# =========================
# RUN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
