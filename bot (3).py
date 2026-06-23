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
PROFILE_STATE = {}
PROFILE_DATA = {}

SYSTEM_PROMPT = """
Ты - Анастасия, опытный AI карьерный консультант с 10-летним опытом в HR и карьерном коучинге.

Твои компетенции:
- Создание профессиональных резюме и CV под конкретные вакансии
- Подготовка к собеседованиям (вопросы, ответы, поведение)
- Анализ рынка труда и поиск вакансий
- Построение карьерной стратегии на 1-3-5 лет
- Помощь при смене профессии
- Развитие навыков и устранение пробелов

Стиль общения:
- Говори как живой человек, не как робот
- Будь тёплой, поддерживающей, но конкретной
- Давай практические советы, не общие фразы
- Если нужна информация - задавай ОДИН конкретный вопрос
- Используй примеры из реальной жизни
- Отвечай на русском языке

Важно:
- Никогда не говори "я не могу" - всегда предлагай альтернативу
- Если человек расстроен или тревожится - сначала поддержи, потом советуй
- Конкретные цифры и факты лучше общих слов
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
                usage_count INTEGER DEFAULT 0,
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
            user_id, username,
            data.get("name"), data.get("age"),
            data.get("experience"), data.get("field"),
            data.get("goal"), data.get("location"),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("SAVE USER ERROR:", str(e))


def increment_usage(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, usage_count)
            VALUES (%s, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                usage_count = users.usage_count + 1,
                updated_at = NOW()
        """, (user_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("INCREMENT ERROR:", str(e))


def delete_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DELETE USER ERROR:", str(e))


def build_system_prompt(profile):
    if not profile:
        return SYSTEM_PROMPT
    extra = "\n\nПрофиль пользователя (используй для персональных советов):\n"
    if profile.get("name"):
        extra += "Имя: " + str(profile["name"]) + "\n"
    if profile.get("age"):
        extra += "Возраст: " + str(profile["age"]) + " лет\n"
    if profile.get("experience"):
        extra += "Опыт работы: " + str(profile["experience"]) + "\n"
    if profile.get("field"):
        extra += "Сфера деятельности: " + str(profile["field"]) + "\n"
    if profile.get("goal"):
        extra += "Карьерная цель: " + str(profile["goal"]) + "\n"
    if profile.get("location"):
        extra += "Город/регион: " + str(profile["location"]) + "\n"
    extra += "\nОбращайся к пользователю по имени. Учитывай его профиль во всех советах."
    return SYSTEM_PROMPT + extra


def ask_gpt(user_id, user_message, profile=None):
    if user_id not in USER_HISTORY:
        USER_HISTORY[user_id] = []

    USER_HISTORY[user_id].append({"role": "user", "content": user_message})

    if len(USER_HISTORY[user_id]) > 20:
        USER_HISTORY[user_id] = USER_HISTORY[user_id][-20:]

    system = build_system_prompt(profile)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + USER_HISTORY[user_id],
        max_tokens=1500,
    )

    reply = response.choices[0].message.content
    USER_HISTORY[user_id].append({"role": "assistant", "content": reply})
    increment_usage(user_id)
    return reply


def get_main_keyboard(has_profile=False):
    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume"),
         InlineKeyboardButton("💼 Найти работу", callback_data="job")],
        [InlineKeyboardButton("🎯 Карьерная стратегия", callback_data="strategy"),
         InlineKeyboardButton("🎤 Подготовка к интервью", callback_data="interview")],
        [InlineKeyboardButton("🔄 Сменить профессию", callback_data="career_change"),
         InlineKeyboardButton("📊 Анализ навыков", callback_data="skills")],
    ]
    if has_profile:
        keyboard.append([InlineKeyboardButton("👤 Мой профиль", callback_data="show_profile")])
    else:
        keyboard.append([InlineKeyboardButton("👤 Заполнить профиль", callback_data="fill_profile")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context):
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "друг"
    profile = get_user(user_id)

    if profile and profile.get("name"):
        text = "С возвращением, " + profile["name"] + "! Чем могу помочь сегодня?"
    else:
        text = (
            "Привет, " + name + "! Я Анастасия — ваш персональный AI карьерный консультант.\n\n"
            "Помогу с резюме, подготовкой к интервью, поиском работы и карьерной стратегией.\n\n"
            "Выберите с чего начнём:"
        )

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(has_profile=bool(profile and profile.get("name")))
    )


async def reset_cmd(update: Update, context):
    user_id = update.effective_user.id
    delete_user(user_id)
    if user_id in USER_HISTORY:
        del USER_HISTORY[user_id]
    if user_id in PROFILE_STATE:
        del PROFILE_STATE[user_id]
    if user_id in PROFILE_DATA:
        del PROFILE_DATA[user_id]
    await update.message.reply_text(
        "Профиль и история удалены. Напишите /start чтобы начать заново."
    )


async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""

    if q.data == "fill_profile":
        PROFILE_STATE[user_id] = "name"
        PROFILE_DATA[user_id] = {}
        await q.message.reply_text(
            "Отлично! Заполним ваш профиль — это займёт 1 минуту и поможет мне давать персональные советы.\n\nКак вас зовут?"
        )
        return

    if q.data == "show_profile":
        profile = get_user(user_id)
        if not profile:
            await q.message.reply_text("Профиль не найден. Заполните его через меню.")
            return
        text = "👤 Ваш профиль:\n\n"
        text += "Имя: " + str(profile.get("name") or "—") + "\n"
        text += "Возраст: " + str(profile.get("age") or "—") + "\n"
        text += "Опыт: " + str(profile.get("experience") or "—") + "\n"
        text += "Сфера: " + str(profile.get("field") or "—") + "\n"
        text += "Цель: " + str(profile.get("goal") or "—") + "\n"
        text += "Город: " + str(profile.get("location") or "—") + "\n"
        text += "Обращений: " + str(profile.get("usage_count") or 0) + "\n\n"
        text += "Чтобы обновить профиль — нажмите кнопку ниже."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Обновить профиль", callback_data="fill_profile")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ])
        await q.message.reply_text(text, reply_markup=keyboard)
        return

    if q.data == "back_to_menu":
        profile = get_user(user_id)
        await q.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(has_profile=bool(profile and profile.get("name")))
        )
        return

    topics = {
        "resume": "Помоги мне создать профессиональное резюме. Спроси что нужно для начала.",
        "job": "Помоги мне найти работу. Спроси о моих предпочтениях.",
        "strategy": "Помоги мне построить карьерную стратегию на ближайший год.",
        "interview": "Помоги мне подготовиться к собеседованию. Спроси детали.",
        "career_change": "Я хочу сменить профессию. Помоги мне разобраться с этим.",
        "skills": "Сделай анализ моих навыков и скажи что нужно развить.",
    }

    if q.data in topics:
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия думает...")
        try:
            reply = ask_gpt(user_id, topics[q.data], profile)
            await q.message.reply_text(reply)
        except Exception as e:
            print("GPT ERROR:", str(e))
            await q.message.reply_text("Произошла ошибка. Попробуйте ещё раз.")


async def chat(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    text = update.message.text

    if user_id in PROFILE_STATE:
        step = PROFILE_STATE[user_id]

        if step == "name":
            PROFILE_DATA[user_id]["name"] = text
            PROFILE_STATE[user_id] = "age"
            await update.message.reply_text("Приятно познакомиться, " + text + "! Сколько вам лет?")
            return

        if step == "age":
            try:
                PROFILE_DATA[user_id]["age"] = int(text)
            except Exception:
                PROFILE_DATA[user_id]["age"] = None
            PROFILE_STATE[user_id] = "experience"
            await update.message.reply_text("Сколько лет вы работаете? Или в какой сфере? (например: 3 года в маркетинге)")
            return

        if step == "experience":
            PROFILE_DATA[user_id]["experience"] = text
            PROFILE_STATE[user_id] = "field"
            await update.message.reply_text("В какой сфере вы сейчас работаете или хотите работать?")
            return

        if step == "field":
            PROFILE_DATA[user_id]["field"] = text
            PROFILE_STATE[user_id] = "goal"
            await update.message.reply_text(
                "Какая ваша главная карьерная цель прямо сейчас?\n"
                "(например: найти работу, повышение, смена профессии, свой бизнес)"
            )
            return

        if step == "goal":
            PROFILE_DATA[user_id]["goal"] = text
            PROFILE_STATE[user_id] = "location"
            await update.message.reply_text("И последнее — из какого вы города?")
            return

        if step == "location":
            PROFILE_DATA[user_id]["location"] = text
            del PROFILE_STATE[user_id]
            save_user(user_id, username, PROFILE_DATA[user_id])
            name = PROFILE_DATA[user_id].get("name", "")
            del PROFILE_DATA[user_id]

            await update.message.reply_text(
                "Профиль сохранён! Теперь я смогу давать вам персональные советы.\n\nЧем займёмся?",
                reply_markup=get_main_keyboard(has_profile=True)
            )
            return

    profile = get_user(user_id)
    await update.message.reply_text("Анастасия думает...")
    try:
        reply = ask_gpt(user_id, text, profile)
        await update.message.reply_text(reply)
    except Exception as e:
        print("GPT ERROR:", str(e))
        await update.message.reply_text("Произошла ошибка. Попробуйте ещё раз.")


def main():
    init_db()
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    print("HEALTH SERVER RUNNING ON PORT " + str(PORT))
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
