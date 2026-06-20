import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# -------------------------
# MEMORY (простая логика состояния)
# -------------------------
USER_STATE = {}

# -------------------------
# START
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🟢 FREE режим", callback_data="mode_free")],
        [InlineKeyboardButton("🟡 PRO режим", callback_data="mode_pro")],
        [InlineKeyboardButton("🔴 VIP режим", callback_data="mode_vip")]
    ]

    await update.message.reply_text(
        "💼 Career System V1\nВыберите режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -------------------------
# HANDLER
# -------------------------
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # =====================
    # SET MODE
    # =====================
    if data.startswith("mode_"):
        USER_STATE[user_id] = {
            "mode": data,
            "step": "menu"
        }

        keyboard = [
            [InlineKeyboardButton("📄 Резюме", callback_data="resume")],
            [InlineKeyboardButton("🏢 Анализ компании", callback_data="company")],
            [InlineKeyboardButton("🔎 Вакансии", callback_data="jobs")],
            [InlineKeyboardButton("🤝 Помощь в собеседовании", callback_data="interview")]
        ]

        await query.message.reply_text(
            f"✅ Режим выбран: {data.upper()}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # =====================
    # GET MODE
    # =====================
    mode = USER_STATE.get(user_id, {}).get("mode", "free")

    # =====================
    # SERVICES (СТАБИЛЬНАЯ ЛОГИКА)
    # =====================

    if data == "resume":
        text = (
            "📄 РЕЗЮМЕ\n\n"
            "Отправьте:\n"
            "- ФИО\n"
            "- Образование\n"
            "- Опыт работы\n"
            "- Должность"
        )

    elif data == "company":
        text = (
            "🏢 АНАЛИЗ КОМПАНИИ\n\n"
            "Отправьте:\n"
            "- Название компании\n"
            "- Город\n\n"
            "Я покажу:\n"
            "- описание\n"
            "- базовые риски\n"
            "- общую информацию"
        )

    elif data == "jobs":
        text = (
            "🔎 ВАКАНСИИ\n\n"
            "Отправьте:\n"
            "- должность\n"
            "- город\n\n"
            "Я дам ссылки на вакансии"
        )

    elif data == "interview":
        text = (
            "🤝 ПОМОЩЬ В СОБЕСЕДОВАНИИ\n\n"
            "Отправьте должность — я дам:\n"
            "- базовые HR вопросы\n"
            "- структуру ответов"
        )

    else:
        text = "Ошибка выбора"

    # защита от дублей (ВАЖНО)
    current_step = USER_STATE.get(user_id, {}).get("step")

    if current_step == data:
        return

    USER_STATE[user_id]["step"] = data

    await query.message.reply_text(text)

# -------------------------
# RUN
# -------------------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
