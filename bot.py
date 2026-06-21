import os
import logging
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# =========================
# STATE
# =========================
USER_MODE = {}
USER_FLOW = {}

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🟢 FREE", callback_data="free")],
        [InlineKeyboardButton("🟡 PRO", callback_data="pro")],
        [InlineKeyboardButton("🔴 VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "💼 CAREER ENGINE v7 (CONNECTOR SYSTEM)\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE SELECTOR
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    mode = q.data

    USER_MODE[user_id] = mode

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 HR", callback_data="interview")],
        [InlineKeyboardButton("🌐 Сайт-визитка", callback_data="site")]
    ]

    await q.message.reply_text(
        f"✅ MODE: {mode.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CORE ENGINE
# =========================
def engine(mode, action):

    # FREE
    if mode == "free":
        return {
            "resume": "📄 FREE резюме (HH формат)",
            "company": "🏢 Базовый анализ компании",
            "jobs": "🔎 Базовые вакансии",
            "interview": "🤝 Базовые HR вопросы",
            "site": "🌐 Простая визитка"
        }[action]

    # PRO (усиленная логика)
    if mode == "pro":
        return {
            "resume": "📄 PRO резюме: опыт + достижения + усиление",
            "company": "🏢 PRO анализ: зарплаты + риски + структура",
            "jobs": "🔎 PRO: сравнение вакансий + стратегия",
            "interview": "🤝 PRO: разбор ответов + улучшение",
            "site": "🌐 PRO сайт-визитка: структура + блоки + CTA"
        }[action]

    # VIP (стратегия)
    return {
        "resume": "📄 VIP: позиционирование кандидата",
        "company": "🏢 VIP: стратегия входа в компанию",
        "jobs": "🔎 VIP: карьерная стратегия",
        "interview": "🤝 VIP: симуляция интервью",
        "site": "🌐 VIP сайт: продающий лендинг + оффер"
    }[action]

# =========================
# 🔥 CONNECTOR ENGINE (ГЛАВНОЕ ИЗ КАРТЫ)
# =========================
def connector(action):

    if action == "resume":
        return [
            "➡️ Рекомендуем: PRO анализ компании",
            "➡️ Или: вакансии под резюме",
            "➡️ Или: HR симулятор"
        ]

    if action == "company":
        return [
            "➡️ Рекомендуем: улучшить резюме под компанию",
            "➡️ Или: вакансии этой сферы",
            "➡️ Или: VIP стратегия"
        ]

    if action == "jobs":
        return [
            "➡️ Рекомендуем: усилить резюме (PRO)",
            "➡️ Или: HR подготовка",
            "➡️ Или: VIP стратегия входа"
        ]

    if action == "interview":
        return [
            "➡️ Рекомендуем: усилить резюме",
            "➡️ Или: вакансии",
            "➡️ Или: VIP стратегия"
        ]

    if action == "site":
        return [
            "➡️ Рекомендуем: создать резюме",
            "➡️ Или: PRO анализ",
            "➡️ Или: вакансии + HR"
        ]

    return []

# =========================
# PAYMENT PLACEHOLDER (НЕ АКТИВЕН)
# =========================
def payment_placeholder():
    return "💳 PAYMENT LAYER: DISABLED (READY FOR FUTURE INTEGRATION)"

# =========================
# HANDLER
# =========================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    action = q.data
    mode = USER_MODE.get(user_id, "free")

    if action in ["resume", "company", "jobs", "interview", "site"]:

        if action == "resume":
            USER_FLOW[user_id] = {"step": 1, "data": {}}
            await q.message.reply_text("📌 Введите ФИО:")
            return

        result = engine(mode, action)
        await q.message.reply_text(result)

        # 🔥 ВАЖНО: СВЯЗИ ИЗ КАРТЫ
        suggestions = connector(action)

        await q.message.reply_text(
            "🔗 СЛЕДУЮЩИЕ ШАГИ:\n\n" + "\n".join(suggestions)
        )

# =========================
# RESUME FLOW
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]

    if flow["step"] == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт работы:")
        return

    if flow["step"] == 2:
        flow["data"]["exp"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование:")
        return

    if flow["step"] == 3:
        flow["data"]["edu"] = text

        USER_FLOW[user_id] = {}

        await update.message.reply_text(
            "📄 РЕЗУЛЬТАТ ГОТОВ\n\n"
            "✔ система завершила обработку\n"
            "🔗 теперь выбери следующий шаг"
        )

# =========================
# RUN
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    app.run_polling()

if __name__ == "__main__":
    main()
