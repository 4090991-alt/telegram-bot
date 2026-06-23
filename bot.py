import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
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
DATABASE_URL = os.getenv("DATABASE_URL")
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

Если у тебя есть информация о профиле пользователя - используй её для персональных советов.
Отвечай на русском языке. Будь дружелюбной, конкретной и полезной.
Давай практические советы. Если нужна дополнительная информация - задавай уточняющие вопросы.
"""


def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                name TEXT,
                age INTEGER,
                experience TEXT,
                field TEXT,
                goal TEXT,
                location TEXT,
                plan TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("DB READY")
    except Exception as e:
        print("DB ERROR:", str(e))


def get_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        print("GET USER ERROR:", str(e))
        return None


def save_user(user_id, username, data):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, name, age, experience, field, goal, location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                experience = EXCLUDED.experience,
                field = EXCLUDED.field,
                goal = EXCLUDED.goal,
                location = EXCLUDED.location,
                updated_at = NOW()
        """, (
            user_id,
            username,
            data.get("name"),
            data.get("age"),
            data.get("experience"),
            data.get("field"),
            data.get("goal"),
            data.get("location"),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("SAVE USER ERROR:", str(e))


def build_system_prompt(profile):
    if not profile:
        return SYSTEM_PROMPT
    extra = "\n\nПрофиль пользователя:\n"
    if profile.get("name"):
        extra += "Имя: " + str(profile["name"]) + "\n"
    if profile.get("age"):
        extra += "Возраст: " + str(profile["age"]) + "\n"
    if profile.get("experience"):
        extra += "Опыт: " + str(profile["experience"]) + "\n"
    if profile.get("field"):
        extra += "Сфера: " + str(profile["field"]) + "\n"
    if profile.get("goal"):
        extra += "Цель: " + str(profile["goal"]) + "\n"
    if profile.get("location"):
        extra += "Локация: " + str(profile["location"]) + "\n"
    return SYSTEM_PROMPT + extra


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


def ask_gpt(user_id, user_message, profile=None):
    if user_id not in USER_HISTORY:
        USER_HISTORY[user_id] = []

    USER_HISTORY[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(USER_HISTORY[user_id]) > 20:
        USER_HISTORY[user_id] = USER_HISTORY[user_id][-20:]

    system = build_system_prompt(profile)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + USER_HISTORY[user_id],
        max_tokens=1000,
    )

    reply = response.choices[0].message.content

    USER_HISTORY[user_id].append({
        "role": "assistant",
        "content": reply
    })

    return reply


PROFILE_STATE = {}
PROFILE_DATA = {}


async def start(update: Update, context):
    user_id = update.effective_user.id
    profile = get_user(user_id)

    if profile:
        name = profile.get("name") or "друг"
        keyboard = [
            [InlineKeyboardButton("Резюме", callback_data="resume")],
            [InlineKeyboardButton("Найти работу", callback_data="job")],
            [InlineKeyboardButton("Карьерная стратегия", callback_data="strategy")],
            [InlineKeyboardButton("Подготовка к интервью", callback_data="interview")],
            [InlineKeyboardButton("Обновить профиль", callback_data="update_profile")],
        ]
        await update.message.reply_text(
            "С возвращением, " + name + "! Чем могу помочь?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        keyboard = [
            [InlineKeyboardButton("Заполнить профиль", callback_data="fill_profile")],
            [InlineKeyboardButton("Начать без профиля", callback_data="skip_profile")],
        ]
        await update.message.reply_text(
            "Привет! Я Анастасия - ваш AI карьерный консультант.\n\nЧтобы давать персональные советы, мне нужно узнать вас лучше.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""

    if q.data == "fill_profile" or q.data == "update_profile":
        PROFILE_STATE[user_id] = "name"
        PROFILE_DATA[user_id] = {}
        await q.message.reply_text("Как вас зовут?")
        return

    if q.data == "skip_profile":
        keyboard = [
            [InlineKeyboardButton("Резюме", callback_data="resume")],
            [InlineKeyboardButton("Найти работу", callback_data="job")],
            [InlineKeyboardButton("Карьерная стратегия", callback_data="strategy")],
            [InlineKeyboardButton("Подготовка к интервью", callback_data="interview")],
        ]
        await q.message.reply_text(
            "Хорошо! Чем могу помочь?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    topics = {
        "resume": "Помоги мне создать профессиональное резюме",
        "job": "Помоги мне найти работу",
        "strategy": "Помоги мне построить карьерную стратегию",
        "interview": "Помоги мне подготовиться к собеседованию",
    }

    if q.data in topics:
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия думает...")
        reply = ask_gpt(user_id, topics[q.data], profile)
        await q.message.reply_text(reply)


async def chat(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    text = update.message.text

    if user_id in PROFILE_STATE:
        step = PROFILE_STATE[user_id]

        if step == "name":
            PROFILE_DATA[user_id]["name"] = text
            PROFILE_STATE[user_id] = "age"
            await update.message.reply_text("Сколько вам лет?")
            return

        if step == "age":
            try:
                PROFILE_DATA[user_id]["age"] = int(text)
            except Exception:
                PROFILE_DATA[user_id]["age"] = None
            PROFILE_STATE[user_id] = "experience"
            await update.message.reply_text("Какой у вас опыт работы? (например: 3 года в IT)")
            return

        if step == "experience":
            PROFILE_DATA[user_id]["experience"] = text
            PROFILE_STATE[user_id] = "field"
            await update.message.reply_text("В какой сфере вы работаете?")
            return

        if step == "field":
            PROFILE_DATA[user_id]["field"] = text
            PROFILE_STATE[user_id] = "goal"
            await update.message.reply_text("Какая ваша карьерная цель? (деньги / рост / смена профессии / другое)")
            return

        if step == "goal":
            PROFILE_DATA[user_id]["goal"] = text
            PROFILE_STATE[user_id] = "location"
            await update.message.reply_text("Из какого вы города?")
            return

        if step == "location":
            PROFILE_DATA[user_id]["location"] = text
            del PROFILE_STATE[user_id]

            save_user(user_id, username, PROFILE_DATA[user_id])
            profile = PROFILE_DATA[user_id]
            del PROFILE_DATA[user_id]

            keyboard = [
                [InlineKeyboardButton("Резюме", callback_data="resume")],
                [InlineKeyboardButton("Найти работу", callback_data="job")],
                [InlineKeyboardButton("Карьерная стратегия", callback_data="strategy")],
                [InlineKeyboardButton("Подготовка к интервью", callback_data="interview")],
            ]
            await update.message.reply_text(
                "Профиль сохранён! Теперь я буду давать персональные советы.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

    profile = get_user(user_id)
    await update.message.reply_text("Анастасия думает...")
    try:
        reply = ask_gpt(user_id, text, profile)
        await update.message.reply_text(reply)
    except Exception as e:
        print("GPT ERROR:", str(e))
        await update.message.reply_text("Извините, произошла ошибка. Попробуйте ещё раз.")


def main():
    init_db()

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
