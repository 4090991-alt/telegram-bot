import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🟢 FREE режим", callback_data="mode_free")],
        [InlineKeyboardButton("🟡 PRO режим", callback_data="mode_pro")],
        [InlineKeyboardButton("🔴 VIP режим", callback_data="mode_vip")]
    ]

    await update.message.reply_text(
        "💼 Career System\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# SINGLE CALLBACK HANDLER (ВАЖНО)
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # =========================
    # STEP 1: MODE SELECT
    # =========================
    if data.startswith("mode_"):

        mode = data.replace("mode_", "")

        keyboard = [
            [InlineKeyboardButton("📄 Резюме FREE", callback_data=f"{mode}_resume")],
            [InlineKeyboardButton("📄 Резюме PRO", callback_data=f"{mode}_resume_pro")],
            [InlineKeyboardButton("🏢 Анализ компании", callback_data=f"{mode}_company")],
            [InlineKeyboardButton("🔎 Вакансии", callback_data=f"{mode}_jobs")],
            [InlineKeyboardButton("🤝 Помощь в собеседовании", callback_data=f"{mode}_interview")]
        ]

        await query.message.reply_text(
            f"📌 Режим выбран: {mode.upper()}\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # =========================
    # STEP 2: ACTIONS
    # =========================
    if "resume" in data:
        text = "📄 Резюме — создание и формат HH"

    elif "company" in data:
        text = "🏢 Анализ компании — описание, риски, зарплаты"

    elif "jobs" in data:
        text = "🔎 Вакансии — подбор и ссылки"

    elif "interview" in data:
        text = "🤝 Помощь в собеседовании — подготовка HR"

    else:
        text = "Ошибка"

    keyboard = [
        [InlineKeyboardButton("💳 Продолжить", callback_data=f"pay_{data}")]
    ]

    await query.message.reply_text(
        f"{text}\n\n💰 Готово к оплате",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return

    # =========================
    # STEP 3: PAYMENT (LOGIC ONLY)
    # =========================
    if data.startswith("pay_"):

        service = data.replace("pay_", "")

        await query.message.reply_text(
            f"""
💳 ОПЛАТА

Услуга: {service}
Сумма: 10 ₽

👉 дальше подключим Tinkoff Pay
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
