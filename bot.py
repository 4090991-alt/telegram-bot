import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from openai import OpenAI

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# KEYS
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# AI ROLE
# =========================

SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный HR-консультант.

Ты помогаешь:
- резюме
- вакансии
- анализ компаний
- собеседования

Правила:
- женский род
- без выдумок
- один ответ = один результат
"""

# =========================
# CRM SIMPLE
# =========================

FREE_LIMIT = 5
user_usage = {}
paid_users = set()

def allowed(user_id):
    return user_id in paid_users or user_usage.get(user_id, 0) < FREE_LIMIT

def add_usage(user_id):
    if user_id not in paid_users:
        user_usage[user_id] = user_usage.get(user_id, 0) + 1

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я АНАСТАСИЯ — карьерный HR-ассистент.\n"
        "Напишите /services"
    )

# =========================
# SERVICES
# =========================

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 Резюме — 2490₽", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ компании — 1490₽", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование — 990₽", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 УСЛУГИ АНАСТАСИИ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK HANDLER
# =========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "paid":
        user_id = query.from_user.id
        paid_users.add(user_id)

        await query.message.reply_text(
            "✅ Оплата подтверждена!\nДоступ открыт."
        )
        return

    texts = {
        "resume": "📄 РЕЗЮМЕ — 2490₽",
        "company": "🏢 АНАЛИЗ КОМПАНИИ — 1490₽",
        "interview": "🎤 СОБЕСЕДОВАНИЕ — 990₽"
    }

    text = texts.get(query.data, "Ошибка")

    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid")]
    ]

    await query.message.reply_text(
        text + "\n\nОплата: СБП / карта XXXX XXXX XXXX",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CHAT AI
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not allowed(user_id):
        await update.message.reply_text("Лимит исчерпан. /services")
        return

    add_usage(user_id)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )

        await update.message.reply_text(
            response.choices[0].message.content[:3500]
        )

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Ошибка сервера")

# =========================
# APP
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("services", services))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
