import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

USER_STATE = {}

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("FREE режим", callback_data="mode_free")],
        [InlineKeyboardButton("PRO режим", callback_data="mode_pro")],
        [InlineKeyboardButton("VIP режим", callback_data="mode_vip")]
    ]

    await update.message.reply_text(
        "Career System\nВыберите режим:",
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

    # SET MODE
    if data.startswith("mode_"):
        USER_STATE[user_id] = {"mode": data}

        keyboard = [
            [InlineKeyboardButton("Резюме", callback_data="resume")],
            [InlineKeyboardButton("Компания", callback_data="company")],
            [InlineKeyboardButton("Вакансии", callback_data="jobs")],
            [InlineKeyboardButton("Собеседование", callback_data="interview")]
        ]

        await query.message.reply_text(
            f"Режим выбран: {data}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    mode = USER_STATE.get(user_id, {}).get("mode", "free")

    # SIMPLE RESPONSE (СТАБИЛЬНАЯ ВЕРСИЯ)
    if data == "resume":
        text = "Резюме: отправьте ФИО, опыт, образование"

    elif data == "company":
        text = "Компания: укажите название и город"

    elif data == "jobs":
        text = "Вакансии: укажите должность и город"

    elif data == "interview":
        text = "Собеседование: включено (PRO/VIP логика позже)"

    else:
        text = "Ошибка"

    await query.message.reply_text(text)

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

app.run_polling()
