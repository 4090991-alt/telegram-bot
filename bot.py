import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

PRICES = {
    "resume": 10,
    "company": 10,
    "interview": 10
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📄 Резюме (10₽)", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания (10₽)", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование (10₽)", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 Выберите услугу:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service = query.data
    price = PRICES.get(service, 10)

    text = f"""
💳 Услуга: {service}
💰 Цена: {price} ₽

👉 Тестовый режим оплаты (обкатка)
"""

    await query.message.reply_text(text)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
