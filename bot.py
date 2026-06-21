import os
import logging

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
        "💼 CAREER ENGINE V6 (CONNECTOR SYSTEM)\n\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MODE SELECTOR
# =========================
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    USER_MODE[q.from_user.id] = q.data

    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
        [InlineKeyboardButton("🏢 Компания", callback_data="company")],
        [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
        [InlineKeyboardButton("🤝 Интервью", callback_data="interview")]
    ]

    await q.message.reply_text(
        f"✅ MODE: {q.data.upper()}\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ENGINE (NO DEAD LOGIC)
# =========================
def engine(mode, action):

    base = {
        "free": {
            "resume": "📄 FREE резюме (HH формат)",
            "company": "🏢 Базовый анализ компании",
            "jobs": "🔎 Базовые вакансии",
            "interview": "🤝 Базовые HR вопросы"
        },
        "pro": {
            "resume": "📄 PRO резюме: опыт + достижения + усиление",
            "company": "🏢 PRO анализ: зарплаты + риски + структура",
            "jobs": "🔎 PRO подбор: сравнение + стратегия рынка",
            "interview": "🤝 PRO интервью: разбор + улучшение ответов"
        },
        "vip": {
            "resume": "📄 VIP стратегия позиционирования",
            "company": "🏢 VIP стратегия входа в компанию",
            "jobs": "🔎 VIP карьерная стратегия",
            "interview": "🤝 VIP симуляция + стресс интервью"
        }
    }

    return base.get(mode, base["free"]).get(action, "❌ действие не найдено")

# =========================
# CONNECTOR MAP (ГЛАВНАЯ ЛОГИКА СХЕМЫ)
# =========================
def connector(action):

    map_flow = {
        "resume": [
            "➡️ PRO анализ компании",
            "➡️ подбор вакансий",
            "➡️ HR интервью"
        ],
        "company": [
            "➡️ улучшить резюме под рынок",
            "➡️ вакансии отрасли",
            "➡️ VIP стратегия входа"
        ],
        "jobs": [
            "➡️ усилить резюме",
            "➡️ HR подготовка",
            "➡️ VIP стратегия"
        ],
        "interview": [
            "➡️ усилить резюме",
            "➡️ вакансии",
            "➡️ VIP стратегия"
        ]
    }

    return map_flow.get(action, [])

# =========================
# ROUTER (SAFE FIXED)
# =========================
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query

    if not q:
        return

    await q.answer()

    user_id = q.from_user.id
    action = q.data
    mode = USER_MODE.get(user_id, "free")

    # INIT FLOW
    if action == "resume":
        USER_FLOW[user_id] = {"step": 1, "data": {}}
        await q.message.reply_text("📌 Введите ФИО и должность:")
        return

    # ENGINE RESPONSE
    result = engine(mode, action)
    await q.message.reply_text(result)

    # CONNECTOR (NEVER EMPTY RESPONSE FLOW)
    next_steps = connector(action)

    if next_steps:
        await q.message.reply_text(
            "🔗 СЛЕДУЮЩИЕ ШАГИ:\n" + "\n".join(next_steps)
        )
    else:
        await q.message.reply_text("➡️ Выберите следующий модуль в меню")

# =========================
# RESUME FLOW (SAFE NO DEADLOCK)
# =========================
async def resume_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in USER_FLOW:
        return

    flow = USER_FLOW[user_id]
    step = flow.get("step", 1)

    if step == 1:
        flow["data"]["fio"] = text
        flow["step"] = 2
        await update.message.reply_text("📌 Опыт работы:")
        return

    if step == 2:
        flow["data"]["exp"] = text
        flow["step"] = 3
        await update.message.reply_text("📌 Образование:")
        return

    if step == 3:
        flow["data"]["edu"] = text

        USER_FLOW[user_id] = {}

        await update.message.reply_text(
            "📄 ГОТОВО\n\n"
            "✔ резюме собрано\n"
            "➡️ теперь выбери: PRO анализ / вакансии / интервью"
        )

# =========================
# MAIN
# =========================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_handler, pattern="^(free|pro|vip)$"))
    app.add_handler(CallbackQueryHandler(action_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    app.run_polling()

if __name__ == "__main__":
    main()
