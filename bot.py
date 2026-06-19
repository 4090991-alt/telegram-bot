import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# ─────────────────────────────
# 🔑 KEYS
# ─────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────────
# 🧠 SYSTEM PROMPT (АНАСТАСИЯ)
# ─────────────────────────────
SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный консультант HR.

Ты помогаешь с:
- резюме
- вакансиями
- анализом компаний
- подготовкой к собеседованиям

Правила:
- всегда женский род (я готова, я помогу)
- не использовать "способен", только "способна"
- не уходить в темы не связанные с карьерой
- не выдумывать информацию
- если данных нет → честно сказать об этом
- давать только 1 результат на запрос
"""

# ─────────────────────────────
# 🚀 START
# ─────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Я Анастасия — ваш карьерный консультант HR. Чем могу помочь?"
    )

# ─────────────────────────────
# 💬 CHAT
# ─────────────────────────────
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7
        )

        answer = response.choices[0].message.content

        await update.message.reply_text(answer[:4000])

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

# ─────────────────────────────
# 🤖 APP
# ─────────────────────────────
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
