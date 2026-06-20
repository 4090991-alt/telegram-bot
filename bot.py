import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# 💰 ЦЕНЫ (обкатка)
PRICES = {
    "resume_basic": 10,
    "resume_pro": 10,
    "company": 10,
    "jobs": 10,
    "interview": 10
}

# =========================
# START MENU (ПОЛНОЕ МЕНЮ)
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📄 Резюме (Базовое)", callback_data="resume_basic")],
        [InlineKeyboardButton("📄 Резюме (Pro)", callback_data="resume_pro")],
        [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
        [InlineKeyboardButton("🔎 Поиск вакансий", callback_data="jobs")],
        [InlineKeyboardButton("🎤 Собеседование", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 AI Career System\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# STEP 2 (УТОЧНЕНИЕ)
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    action = query.data

    # =========================
    # RESUME BASIC
    # =========================
    if action == "resume_basic":
        text = """
📄 РЕЗЮМЕ (БАЗОВОЕ)

✔ Формат HeadHunter
✔ Простая структура
✔ Быстрая генерация

💰 Цена: 10 ₽

👉 Нажмите оплатить
"""
    
    # =========================
    # RESUME PRO
    # =========================
    elif action == "resume_pro":
        text = """
📄 РЕЗЮМЕ (PRO)

✔ Полная структура опыта
✔ Усиление достижений
✔ Профессиональная упаковка

💰 Цена: 10 ₽

👉 Нажмите оплатить
"""

    # =========================
    # COMPANY ANALYSIS
    # =========================
    elif action == "company":
        text = """
🏢 АНАЛИЗ КОМПАНИИ

✔ Описание компании
✔ Риски
✔ Инсайты
✔ Вакансии (если есть)

💰 Цена: 10 ₽

👉 Нажмите оплатить
"""

    # =========================
    # JOBS
    # =========================
    elif action == "jobs":
        text = """
🔎 ПОИСК ВАКАНСИЙ

✔ Подбор вакансий
✔ Ссылки на HH
✔ Анализ требований

💰 Цена: 10 ₽

👉 Нажмите оплатить
"""

    # =========================
    # INTERVIEW
    # =========================
    elif action == "interview":
        text = """
🎤 СОБЕСЕДОВАНИЕ

✔ HR вопросы
✔ Подготовка
✔ Разбор ошибок

💰 Цена: 10 ₽

👉 Нажмите оплатить
"""

    # =========================
    # PAYMENT BUTTON (ФИНАЛЬНЫЙ ШАГ)
    # =========================
    keyboard = [
        [InlineKeyboardButton("💳 ОПЛАТИТЬ 10₽", callback_data=f"pay_{action}")]
    ]

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# PAYMENT STEP (ПОКА ЗАГЛУШКА, НО ПРАВИЛЬНАЯ ЛОГИКА)
# =========================
async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    action = query.data.replace("pay_", "")

    await query.message.reply_text(
        f"""
💳 ОПЛАТА ЗАПУЩЕНА

Услуга: {action}
Сумма: 10 ₽

👉 Здесь позже подключается Tinkoff Pay
👉 После оплаты откроется результат
"""
    )


# =========================
# RUN APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(payment, pattern="pay_"))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
