import os
import logging
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# =========================
# STATE
# =========================
USER_STATE = {}

# =========================
# TEST PAYMENT (STABLE MODE)
# =========================
def create_payment(user_id, service, amount=10):

    # 💣 ТЕСТОВАЯ СИСТЕМА (без банка, без API)
    fake_url = f"https://pay.test.local/pay?user={user_id}&service={service}&amount={amount}"

    return fake_url


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
        "💼 Career System STABLE V1 (TEST MODE)",
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

    USER_STATE[user_id] = data

    # =========================
    # PAYMENT FLOW (TEST)
    # =========================
    payment_url = create_payment(user_id, data, 10)

    await query.message.reply_text(
        f"""
💳 Услуга: {data}
💰 Цена: 10₽ (TEST MODE)

👉 Ссылка оплаты:
{payment_url}

⚠️ Это тестовый режим (без реальной оплаты)

После оплаты (симуляция) будет следующий этап V3.
"""
    )


# =========================
# RUN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
