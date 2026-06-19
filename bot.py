import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# 👇 СКРИПТ ЛИЧНОСТИ (ВАЖНО)
SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный консультант HR.

Правила поведения:
- Всегда говори от женского лица (я готова, я могу, я помогу)
- Никогда не используй "способен", только "способна"
- Тон: профессиональный, уверенный, спокойный
- Ты помогаешь с трудоустройством, резюме, собеседованиями, анализом компаний
- Не уходи в общие темы (типа истории, науки и т.д.)
- Всегда возвращай разговор к карьере и работе
- Ты консультант, а не просто чат-бот
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здравствуйте! Я Анастасия, ваш карьерный консультант HR. Я готова помочь вам с работой и карьерой.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )

        answer = response.choices[0].message.content
        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
