import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    print("NO TOKEN FOUND")
    raise SystemExit()

if not OPENAI_API_KEY:
    print("NO OPENAI KEY FOUND")
    raise SystemExit()

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
print("BOT STARTED OK")

USER_HISTORY = {}

SYSTEM_PROMPT = """
Ты - Анастасия, AI карьерный консультант.
Ты помогаешь людям:
- Создавать профессиональные резюме и CV
- Готовиться к собеседованиям
- Находить работу и анализировать вакансии
- Строить карьерную стратегию
- Менять профессию

Отвечай на русском языке. Будь дружелюбной, конкретной и полезной.
Давай практические советы. Если нужна дополнительная информация - задавай уточняющие вопросы.
"""


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


def ask_gpt(user_id, user_message):
    if user_id not in USER_HISTORY:
        USER_HISTORY[user_id] = []

    USER_HISTORY[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(USER_HISTORY[user_id]) > 20:
        USER_HISTORY[user_id] = USER_HISTORY[user_id][-20:]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + USER_HISTORY[user_id],
        max_tokens=1000,
    )

    reply = response.choices[0].message.content

    USER_HISTORY[user_id].append({
        "role": "assistant",
        "content": reply
    })

    return reply


async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Резюме", callback_data="resume")],
        [InlineKeyboardButton("Найти работу", callback_data="job")],
        [InlineKeyboardButton("Карьерная стратегия", callback_data="strategy")],
        [InlineKeyboardButton("Подготовка к интервью", callback_data="interview")],
    ]
    await update.message.reply_text(
        "Привет! Я Анастасия - ваш AI карьерный консультант.\n\nЧем могу помочь?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    topics = {
        "resume": "Помоги мне создать профессиональное резюме",
        "job": "Помоги мне найти работу",
        "strategy": "Помоги мне построить карьерную стратегию",
        "interview": "Помоги мне подготовиться к собеседованию",
    }

    if q.data in topics:
        await q.message.reply_text("Анастасия думает...")
        reply = ask_gpt(user_id, topics[q.data])
        await q.message.reply_text(reply)


async def chat(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text
    await update.message.reply_text("Анастасия думает...")
    try:
        reply = ask_gpt(user_id, text)
        await update.message.reply_text(reply)
    except Exception as e:
        print("GPT ERROR:", str(e))
        await update.message.reply_text("Извините, произошла ошибка. Попробуйте ещё раз.")


def main():
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    print("HEALTH SERVER RUNNING ON PORT " + str(PORT))

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
