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
        [InlineKeyboardButton("🔴 VIP режим", callback_data="mode_vip")],
    ]

    await update.message.reply_text(
        "💼 Career AI System\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# MODE SELECT
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    mode = query.data

    # =========================
    # SERVICES MENU
    # =========================
    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data=f"{mode}_resume")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data=f"{mode}_company")],
        [InlineKeyboardButton("🔎 Поиск вакансий", callback_data=f"{mode}_jobs")],
        [InlineKeyboardButton("🤝 Помощь в собеседовании", callback_data=f"{mode}_interview")]
    ]

    mode_name = {
        "mode_free": "FREE",
        "mode_pro": "PRO",
        "mode_vip": "VIP"
    }[mode]

    await query.message.reply_text(
        f"📌 Режим: {mode_name}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ACTION HANDLER
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # FIX: понятные тексты
    texts = {
        "resume": "📄 Резюме — создание и улучшение",
        "company": "🏢 Анализ компании — риски, зарплаты, описание",
        "jobs": "🔎 Поиск вакансий — подбор и ссылки",
        "interview": "🤝 Помощь в собеседовании — вопросы и подготовка"
    }

    # извлекаем действие
    action = data.split("_")[1]

    text = texts.get(action, "Ошибка")

    keyboard = [
        [InlineKeyboardButton("💳 Продолжить", callback_data=f"pay_{data}")]
    ]

    await query.message.reply_text(
        f"{text}\n\n💰 Доступ зависит от выбранного режима",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# PAYMENT STEP (ЗАГЛУШКА ПОКА)
# =========================
async def pay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data.replace("pay_", "")

    await query.message.reply_text(
        f"""
💳 ОПЛАТА

Услуга: {data}

👉 Здесь будет Tinkoff Pay
👉 После оплаты откроется результат
"""
    )


# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(mode_handler, pattern="mode_"))
app.add_handler(CallbackQueryHandler(action_handler, pattern=".*_(resume|company|jobs|interview)$"))
app.add_handler(CallbackQueryHandler(pay_handler, pattern="pay_"))

app.run_polling()
