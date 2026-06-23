import os
import logging
import threading
import json
import httpx
import tempfile
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
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
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

PROFILE_STATE = {}
PROFILE_DATA = {}

# =====================
# ВОПРОСЫ ДЛЯ ПРОФИЛЯ
# =====================
QUESTIONS = {
    "language": {
        "text": "Привет! Я Анастасия — ваш персональный карьерный консультант 🤝\n\nНа каком языке вам удобнее общаться?",
        "keyboard": [["🇷🇺 Русский", "🇬🇧 English", "🇨🇳 中文"]]
    },
    "name": "Как вас зовут? (Имя или Имя Фамилия)",
    "age": "Сколько вам лет?",
    "city": "Из какого вы города?",
    "status": {
        "text": "Вы сейчас:",
        "keyboard": [["💼 Работаю", "🔍 В поиске работы"], ["🎓 Учусь", "🏠 Не работаю"]]
    },
    "profession": None,  # динамический
    "experience_years": "Сколько лет общего опыта работы? (введите число, например: 5)\n\nЕсли опыта нет — напишите 0",
    "field": None,  # динамический
    "goal": {
        "text": "Какая ваша главная цель прямо сейчас?",
        "keyboard": [
            ["🎯 Найти работу", "⬆️ Повышение / рост"],
            ["🔄 Сменить профессию", "💰 Увеличить доход"],
            ["🚀 Свой бизнес", "📚 Учиться / развиваться"]
        ]
    },
    "salary": "Какой уровень желаемой зарплаты? (например: от 80 000 руб или $2000)",
    "work_format": {
        "text": "Какой формат работы предпочитаете?",
        "keyboard": [["🏢 Офис", "🏠 Удалёнка", "🔀 Гибрид"]]
    },
    "relocation": {
        "text": "Готовы к переезду или командировкам?",
        "keyboard": [["✅ Да, готов(а)", "🏙️ Только командировки", "❌ Нет"]]
    },
    "limitations": "Есть ли у вас какие-либо ограничения, которые важно учитывать при поиске работы?\n(здоровье, физические, возрастные и т.д.)\n\nЕсли нет — напишите «нет»",
    "languages": "Какие языки знаете и на каком уровне?\n(например: Русский — родной, Английский — B1)\n\nЕсли только русский — напишите «только русский»",
    "driver_license": {
        "text": "Есть водительское удостоверение?",
        "keyboard": [["🚗 Да, категория B", "🚛 Да, C/D/E", "❌ Нет"]]
    },
    "education": "Какое у вас образование?\n(уровень и специальность, например: Высшее, менеджмент)",
    "skills": None,  # динамический
    "resume_language": {
        "text": "На каком языке создавать резюме?",
        "keyboard": [["🇷🇺 Русский", "🇬🇧 English", "📄 Оба варианта"]]
    },
    "achievements": None,  # динамический
    "photo": {
        "text": "Есть фото для резюме?",
        "keyboard": [["📸 Да, загружу", "❌ Нет фото"]]
    }
}

PROFILE_STEPS = [
    "language", "name", "age", "city", "status",
    "profession", "experience_years", "field", "goal",
    "salary", "work_format", "relocation", "limitations",
    "languages", "driver_license", "education", "skills",
    "resume_language", "achievements", "photo"
]


def get_dynamic_question(step, profile_data):
    exp = profile_data.get("experience_years", 0)
    try:
        exp = int(exp)
    except Exception:
        exp = 0

    status = profile_data.get("status", "")
    name = profile_data.get("name", "")

    if step == "profession":
        if exp == 0 or "учусь" in status.lower():
            return "Кем вы хотите работать? Какая профессия вас интересует?"
        else:
            return "Какая у вас профессия или должность?"

    if step == "field":
        if exp == 0:
            return "В какой сфере хотите строить карьеру?"
        else:
            return "В какой сфере вы работали больше всего?"

    if step == "skills":
        if exp == 0:
            return (
                "Перечислите ваши навыки, знания и инструменты:\n"
                "(программы, курсы, хобби, стажировки — всё важно!)"
            )
        elif exp >= 10:
            return (
                "Перечислите ваши ключевые навыки и инструменты:\n"
                "(включая управленческие, стратегические, технические)"
            )
        else:
            return "Перечислите ваши ключевые навыки и инструменты:"

    if step == "achievements":
        if exp == 0:
            return (
                "Есть ли у вас достижения, которые стоит выделить?\n"
                "(награды, проекты, волонтёрство, успехи в учёбе)\n\n"
                "Если нет — напишите «нет»"
            )
        elif exp >= 10:
            return (
                "Какие ваши главные достижения в цифрах?\n"
                "(например: увеличил продажи на 35%, управлял командой 15 человек)\n\n"
                "Цифры и факты делают резюме сильным!"
            )
        else:
            return (
                "Какие ваши достижения на предыдущих местах работы?\n"
                "(желательно в цифрах: увеличил, снизил, внедрил)\n\n"
                "Если нет — напишите «нет»"
            )

    return None


# =====================
# REDIS
# =====================
def redis_get(key):
    try:
        url = REDIS_URL + "/get/" + key
        headers = {"Authorization": "Bearer " + REDIS_TOKEN}
        r = httpx.get(url, headers=headers, timeout=5)
        data = r.json()
        if data.get("result"):
            return json.loads(data["result"])
        return None
    except Exception as e:
        print("REDIS GET ERROR:", str(e))
        return None


def redis_set(key, value, ttl=86400):
    try:
        url = REDIS_URL + "/set/" + key
        headers = {"Authorization": "Bearer " + REDIS_TOKEN}
        payload = json.dumps(value)
        r = httpx.post(url, headers=headers, json=[payload, "EX", ttl], timeout=5)
        return True
    except Exception as e:
        print("REDIS SET ERROR:", str(e))
        return False


def redis_delete(key):
    try:
        url = REDIS_URL + "/del/" + key
        headers = {"Authorization": "Bearer " + REDIS_TOKEN}
        httpx.get(url, headers=headers, timeout=5)
        return True
    except Exception as e:
        print("REDIS DEL ERROR:", str(e))
        return False


def get_history(user_id):
    history = redis_get("history:" + str(user_id))
    return history if history else []


def save_history(user_id, history):
    if len(history) > 20:
        history = history[-20:]
    redis_set("history:" + str(user_id), history, ttl=604800)


def clear_history(user_id):
    redis_delete("history:" + str(user_id))


# =====================
# DATABASE
# =====================
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
                language TEXT DEFAULT 'ru',
                name TEXT,
                age INTEGER,
                city TEXT,
                status TEXT,
                profession TEXT,
                experience_years INTEGER DEFAULT 0,
                field TEXT,
                goal TEXT,
                salary TEXT,
                work_format TEXT,
                relocation TEXT,
                limitations TEXT,
                languages TEXT,
                driver_license TEXT,
                education TEXT,
                skills TEXT,
                resume_language TEXT DEFAULT 'ru',
                achievements TEXT,
                photo TEXT,
                plan TEXT DEFAULT 'free',
                usage_count INTEGER DEFAULT 0,
                profile_complete BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Добавляем новые колонки если их нет
        new_cols = [
            ("language", "TEXT DEFAULT 'ru'"),
            ("city", "TEXT"),
            ("status", "TEXT"),
            ("profession", "TEXT"),
            ("experience_years", "INTEGER DEFAULT 0"),
            ("salary", "TEXT"),
            ("work_format", "TEXT"),
            ("relocation", "TEXT"),
            ("limitations", "TEXT"),
            ("languages", "TEXT"),
            ("driver_license", "TEXT"),
            ("resume_language", "TEXT DEFAULT 'ru'"),
            ("achievements", "TEXT"),
            ("photo", "TEXT"),
            ("profile_complete", "BOOLEAN DEFAULT FALSE"),
            ("usage_count", "INTEGER DEFAULT 0"),
        ]
        for col, col_type in new_cols:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_type}")
            except Exception:
                pass
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


def save_user_field(user_id, username, field, value):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username) VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, username))
        cur.execute(
            f"UPDATE users SET {field} = %s, updated_at = NOW() WHERE user_id = %s",
            (value, user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("SAVE FIELD ERROR:", str(e))


def save_full_profile(user_id, username, data):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (
                user_id, username, language, name, age, city, status,
                profession, experience_years, field, goal, salary,
                work_format, relocation, limitations, languages,
                driver_license, education, skills, resume_language,
                achievements, photo, profile_complete
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, TRUE
            )
            ON CONFLICT (user_id) DO UPDATE SET
                language = EXCLUDED.language,
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                city = EXCLUDED.city,
                status = EXCLUDED.status,
                profession = EXCLUDED.profession,
                experience_years = EXCLUDED.experience_years,
                field = EXCLUDED.field,
                goal = EXCLUDED.goal,
                salary = EXCLUDED.salary,
                work_format = EXCLUDED.work_format,
                relocation = EXCLUDED.relocation,
                limitations = EXCLUDED.limitations,
                languages = EXCLUDED.languages,
                driver_license = EXCLUDED.driver_license,
                education = EXCLUDED.education,
                skills = EXCLUDED.skills,
                resume_language = EXCLUDED.resume_language,
                achievements = EXCLUDED.achievements,
                photo = EXCLUDED.photo,
                profile_complete = TRUE,
                updated_at = NOW()
        """, (
            user_id, username,
            data.get("language", "ru"),
            data.get("name"), data.get("age"), data.get("city"),
            data.get("status"), data.get("profession"),
            data.get("experience_years", 0), data.get("field"),
            data.get("goal"), data.get("salary"), data.get("work_format"),
            data.get("relocation"), data.get("limitations"),
            data.get("languages"), data.get("driver_license"),
            data.get("education"), data.get("skills"),
            data.get("resume_language", "ru"), data.get("achievements"),
            data.get("photo")
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("SAVE PROFILE ERROR:", str(e))


def increment_usage(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users SET usage_count = COALESCE(usage_count, 0) + 1,
            updated_at = NOW() WHERE user_id = %s
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


# =====================
# ПОИСК ВАКАНСИЙ
# =====================
def search_hh(query, location="", experience="", count=5):
    try:
        params = {
            "text": query,
            "per_page": count,
            "order_by": "relevance",
        }
        area_id = get_hh_area_id(location)
        if area_id:
            params["area"] = area_id
        exp_code = map_experience(experience)
        if exp_code:
            params["experience"] = exp_code

        r = httpx.get(
            "https://api.hh.ru/vacancies",
            params=params,
            headers={"User-Agent": "CareerBot/1.0"},
            timeout=10
        )
        data = r.json()
        results = []
        for item in data.get("items", []):
            salary = ""
            if item.get("salary"):
                s = item["salary"]
                if s.get("from") and s.get("to"):
                    salary = str(s["from"]) + "-" + str(s["to"]) + " " + str(s.get("currency", ""))
                elif s.get("from"):
                    salary = "от " + str(s["from"]) + " " + str(s.get("currency", ""))
                elif s.get("to"):
                    salary = "до " + str(s["to"]) + " " + str(s.get("currency", ""))
            results.append({
                "title": item.get("name", ""),
                "company": item.get("employer", {}).get("name", ""),
                "salary": salary,
                "url": item.get("alternate_url", ""),
                "source": "hh.ru"
            })
        return results
    except Exception as e:
        print("HH ERROR:", str(e))
        return []


def get_hh_area_id(location):
    city_map = {
        "москва": "1", "moscow": "1",
        "санкт-петербург": "2", "спб": "2", "питер": "2",
        "екатеринбург": "3", "новосибирск": "4",
        "казань": "88", "нижний новгород": "66",
        "челябинск": "104", "самара": "78",
        "уфа": "99", "ростов": "76",
        "краснодар": "53", "воронеж": "26",
        "пермь": "72", "волгоград": "24",
    }
    loc = str(location).lower().strip()
    for key, val in city_map.items():
        if key in loc:
            return val
    return "113"


def map_experience(exp):
    try:
        years = int(exp)
        if years == 0:
            return "noExperience"
        elif years <= 3:
            return "between1And3"
        elif years <= 6:
            return "between3And6"
        else:
            return "moreThan6"
    except Exception:
        return "between1And3"


def search_all_vacancies(profile):
    query = profile.get("profession") or profile.get("field") or "специалист"
    location = profile.get("city", "")
    experience = profile.get("experience_years", 0)
    results = search_hh(query, location, experience, count=8)
    return results


def format_vacancies(vacancies, profile):
    if not vacancies:
        return "По вашему запросу ничего не найдено. Попробуем изменить параметры поиска."

    name = profile.get("name", "") if profile else ""
    text = ""
    if name:
        text = name + ", вот что я нашла для вас:\n\n"
    else:
        text = "Вот подходящие вакансии:\n\n"

    for i, v in enumerate(vacancies[:8], 1):
        text += str(i) + ". " + v["title"] + "\n"
        if v["company"]:
            text += "   🏢 " + v["company"] + "\n"
        if v["salary"]:
            text += "   💰 " + v["salary"] + "\n"
        text += "   🔗 " + v["url"] + "\n\n"

    text += "Хотите подготовить резюме под конкретную вакансию?"
    return text


# =====================
# GPT
# =====================
def build_system_prompt(profile):
    base = """
Ты - Анастасия, опытный AI карьерный консультант.
Ты — диагност, консультант, подруга, психолог и профессионал в одном лице.
Твой принцип: не продавать — выявлять потребности и помогать через заботу.
Лозунг: "Я рядом, я помогу. Помогу тебе зарабатывать больше."

Стиль: тёплый, живой, конкретный. Один вопрос за раз.
КРИТИЧЕСКИ ВАЖНО: Отвечай СТРОГО на том языке, который выбрал пользователь. Если русский - ТОЛЬКО русский. Если English - ONLY English. Если 中文 - 只用中文. НИКОГДА не смешивай языки!
Никогда не говори "я не могу" — всегда предлагай решение.
Если человек тревожится — сначала поддержи, потом советуй.
"""
    if not profile:
        return base

    exp = profile.get("experience_years", 0)
    try:
        exp = int(exp)
    except Exception:
        exp = 0

    extra = "\n\nПРОФИЛЬ КЛИЕНТА:\n"
    if profile.get("name"):
        extra += "Имя: " + str(profile["name"]) + "\n"
    if profile.get("age"):
        extra += "Возраст: " + str(profile["age"]) + " лет\n"
    if profile.get("city"):
        extra += "Город: " + str(profile["city"]) + "\n"
    if profile.get("status"):
        extra += "Статус: " + str(profile["status"]) + "\n"
    if profile.get("profession"):
        extra += "Профессия: " + str(profile["profession"]) + "\n"

    extra += "Опыт: "
    if exp == 0:
        extra += "без опыта\n"
    else:
        extra += str(exp) + " лет\n"

    if profile.get("field"):
        extra += "Сфера: " + str(profile["field"]) + "\n"
    if profile.get("goal"):
        extra += "Цель: " + str(profile["goal"]) + "\n"
    if profile.get("salary"):
        extra += "Желаемая зарплата: " + str(profile["salary"]) + "\n"
    if profile.get("work_format"):
        extra += "Формат работы: " + str(profile["work_format"]) + "\n"
    if profile.get("relocation"):
        extra += "Переезд/командировки: " + str(profile["relocation"]) + "\n"
    if profile.get("limitations") and profile["limitations"].lower() != "нет":
        extra += "Ограничения: " + str(profile["limitations"]) + "\n"
    if profile.get("languages"):
        extra += "Языки: " + str(profile["languages"]) + "\n"
    if profile.get("driver_license"):
        extra += "Права: " + str(profile["driver_license"]) + "\n"
    if profile.get("education"):
        extra += "Образование: " + str(profile["education"]) + "\n"
    if profile.get("skills"):
        extra += "Навыки: " + str(profile["skills"]) + "\n"
    if profile.get("achievements") and profile["achievements"].lower() != "нет":
        extra += "Достижения: " + str(profile["achievements"]) + "\n"

    extra += "\nОБЯЗАТЕЛЬНО: обращайся по имени, учитывай все данные профиля в каждом ответе."

    if exp == 0:
        extra += "\nВАЖНО: у клиента нет опыта работы. Адаптируй советы для начинающего специалиста."
    elif exp >= 10:
        extra += "\nВАЖНО: у клиента большой опыт 10+ лет. Рекомендуй VIP/PRO форматы, управленческие позиции."

    return base + extra


def ask_gpt(user_id, user_message, profile=None):
    history = get_history(user_id)
    history.append({"role": "user", "content": user_message})
    system = build_system_prompt(profile)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + history,
        max_tokens=1500,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    save_history(user_id, history)
    increment_usage(user_id)
    return reply


async def transcribe_voice(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru"
        )
    return transcript.text


# =====================
# КЛАВИАТУРЫ
# =====================
def get_main_keyboard(profile=None):
    exp = 0
    name = ""
    if profile:
        try:
            exp = int(profile.get("experience_years", 0))
        except Exception:
            exp = 0
        name = profile.get("name", "")

    keyboard = [
        [InlineKeyboardButton("📄 Резюме (бесплатно)", callback_data="resume_free"),
         InlineKeyboardButton("⭐ ПРО резюме", callback_data="resume_pro")],
        [InlineKeyboardButton("👑 VIP резюме", callback_data="resume_vip"),
         InlineKeyboardButton("🔍 Найти вакансии", callback_data="search_jobs")],
        [InlineKeyboardButton("🎤 HR симулятор", callback_data="hr_simulator"),
         InlineKeyboardButton("📊 Анализ компании", callback_data="analyze_company")],
        [InlineKeyboardButton("🌐 Сайт-визитка", callback_data="website"),
         InlineKeyboardButton("📚 Подобрать курсы", callback_data="find_courses")],
        [InlineKeyboardButton("💬 Спросить Анастасию", callback_data="ask_anastasia")],
    ]

    if profile and profile.get("profile_complete"):
        keyboard.append([InlineKeyboardButton("👤 Мой профиль", callback_data="show_profile")])
    else:
        keyboard.append([InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")])

    return InlineKeyboardMarkup(keyboard)


def make_keyboard(options):
    keyboard = []
    for row in options:
        keyboard.append([InlineKeyboardButton(btn, callback_data="ans_" + btn) for btn in row])
    return InlineKeyboardMarkup(keyboard)


# =====================
# HEALTH SERVER
# =====================
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


# =====================
# ПРОФИЛЬ - СБОР ДАННЫХ
# =====================
async def send_next_question(update_or_message, user_id, step, profile_data):
    question_data = QUESTIONS.get(step)

    if question_data is None:
        text = get_dynamic_question(step, profile_data)
        if text:
            if hasattr(update_or_message, 'reply_text'):
                await update_or_message.reply_text(text)
            else:
                await update_or_message.message.reply_text(text)
        return

    if isinstance(question_data, str):
        if hasattr(update_or_message, 'reply_text'):
            await update_or_message.reply_text(question_data)
        else:
            await update_or_message.message.reply_text(question_data)
    elif isinstance(question_data, dict):
        text = question_data["text"]
        keyboard = make_keyboard(question_data["keyboard"])
        if hasattr(update_or_message, 'reply_text'):
            await update_or_message.reply_text(text, reply_markup=keyboard)
        else:
            await update_or_message.message.reply_text(text, reply_markup=keyboard)


async def finish_profile(message, user_id, username, data):
    save_full_profile(user_id, username, data)
    clear_history(user_id)

    exp = 0
    try:
        exp = int(data.get("experience_years", 0))
    except Exception:
        pass

    name = data.get("name", "")

    if exp == 0:
        summary = (
            name + ", ваш профиль заполнен! 🎉\n\n"
            "Я вижу, что вы в начале карьерного пути — это отличное время для старта!\n\n"
            "Что я могу сделать для вас прямо сейчас:\n"
            "📄 Создать резюме для начинающего специалиста\n"
            "🔍 Найти стажировки и вакансии без опыта\n"
            "📚 Подобрать курсы для старта в вашей сфере\n\n"
            "С чего начнём?"
        )
    elif exp >= 10:
        summary = (
            name + ", ваш профиль заполнен! 🎉\n\n"
            "Впечатляющий опыт " + str(exp) + " лет! Вы заслуживаете лучшего.\n\n"
            "Рекомендую:\n"
            "👑 VIP резюме с вашими достижениями\n"
            "🌐 Сайт-визитка для топ-позиций\n"
            "🎤 HR симулятор для руководящих должностей\n\n"
            "С чего начнём?"
        )
    else:
        summary = (
            name + ", ваш профиль заполнен! 🎉\n\n"
            "Теперь я знаю всё необходимое для персональных рекомендаций.\n\n"
            "Что делаем первым?"
        )

    profile = get_user(user_id)
    await message.reply_text(summary, reply_markup=get_main_keyboard(profile))


# =====================
# HANDLERS
# =====================
async def start(update: Update, context):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "друг"
    profile = get_user(user_id)

    if profile and profile.get("profile_complete"):
        name = profile.get("name") or first_name
        await update.message.reply_text(
            "С возвращением, " + name + "! Чем могу помочь сегодня? 😊",
            reply_markup=get_main_keyboard(profile)
        )
    else:
        PROFILE_STATE[user_id] = "language"
        PROFILE_DATA[user_id] = {}
        q = QUESTIONS["language"]
        await update.message.reply_text(
            q["text"],
            reply_markup=make_keyboard(q["keyboard"])
        )


async def reset_cmd(update: Update, context):
    user_id = update.effective_user.id
    delete_user(user_id)
    clear_history(user_id)
    if user_id in PROFILE_STATE:
        del PROFILE_STATE[user_id]
    if user_id in PROFILE_DATA:
        del PROFILE_DATA[user_id]
    await update.message.reply_text(
        "Профиль и история удалены. Напишите /start чтобы начать заново."
    )


async def callback_handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""
    data = q.data

    # Ответ на вопрос профиля через кнопку
    if data.startswith("ans_") and user_id in PROFILE_STATE:
        answer = data[4:]
        step = PROFILE_STATE[user_id]
        PROFILE_DATA[user_id][step] = answer

        idx = PROFILE_STEPS.index(step)
        if idx + 1 < len(PROFILE_STEPS):
            next_step = PROFILE_STEPS[idx + 1]
            PROFILE_STATE[user_id] = next_step
            await send_next_question(q.message, user_id, next_step, PROFILE_DATA[user_id])
        else:
            del PROFILE_STATE[user_id]
            await finish_profile(q.message, user_id, username, PROFILE_DATA[user_id])
            del PROFILE_DATA[user_id]
        return

    if data == "start_profile":
        PROFILE_STATE[user_id] = "language"
        PROFILE_DATA[user_id] = {}
        q2 = QUESTIONS["language"]
        await q.message.reply_text(q2["text"], reply_markup=make_keyboard(q2["keyboard"]))
        return

    if data == "show_profile":
        profile = get_user(user_id)
        if not profile:
            await q.message.reply_text("Профиль не найден.")
            return
        exp = profile.get("experience_years", 0)
        exp_text = "без опыта" if exp == 0 else str(exp) + " лет"
        text = "👤 Ваш профиль:\n\n"
        text += "Имя: " + str(profile.get("name") or "—") + "\n"
        text += "Возраст: " + str(profile.get("age") or "—") + "\n"
        text += "Город: " + str(profile.get("city") or "—") + "\n"
        text += "Профессия: " + str(profile.get("profession") or "—") + "\n"
        text += "Опыт: " + exp_text + "\n"
        text += "Сфера: " + str(profile.get("field") or "—") + "\n"
        text += "Цель: " + str(profile.get("goal") or "—") + "\n"
        text += "Зарплата: " + str(profile.get("salary") or "—") + "\n"
        text += "Формат: " + str(profile.get("work_format") or "—") + "\n"
        text += "Образование: " + str(profile.get("education") or "—") + "\n"
        text += "Навыки: " + str(profile.get("skills") or "—") + "\n"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Обновить профиль", callback_data="start_profile")],
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back_menu")]
        ])
        await q.message.reply_text(text, reply_markup=keyboard)
        return

    if data == "clear_history":
        clear_history(user_id)
        await q.message.reply_text("История очищена.")
        return

    if data == "back_menu":
        profile = get_user(user_id)
        await q.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(profile))
        return

    if data == "search_jobs":
        profile = get_user(user_id)
        if not profile or not profile.get("profile_complete"):
            await q.message.reply_text(
                "Для точного поиска вакансий нужен ваш профиль.\nЗаполните его — займёт 2 минуты!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")
                ]])
            )
            return
        await q.message.reply_text("Ищу вакансии по вашему профилю...")
        vacancies = search_all_vacancies(profile)
        text = format_vacancies(vacancies, profile)
        await q.message.reply_text(text, disable_web_page_preview=True)
        return

    if data == "resume_free":
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия готовит ваше резюме...")
        try:
            prompt = "Создай базовое резюме для пользователя на основе его профиля в формате hh.ru. Структурированно и профессионально."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
            await q.message.reply_text(
                "Хотите улучшить резюме?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ ПРО резюме (платно)", callback_data="resume_pro")],
                    [InlineKeyboardButton("🎤 Подготовиться к интервью", callback_data="hr_simulator")],
                    [InlineKeyboardButton("🔍 Найти вакансии", callback_data="search_jobs")],
                ])
            )
        except Exception as e:
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "resume_pro":
        await q.message.reply_text(
            "⭐ ПРО резюме — платная услуга\n\n"
            "Включает:\n"
            "• ATS-оптимизированное резюме\n"
            "• 2 варианта дизайна на выбор\n"
            "• Анализ и улучшение текста\n"
            "• Сопроводительное письмо\n\n"
            "Функция оплаты скоро будет доступна!\n"
            "Пока вы можете использовать бесплатное резюме.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📄 Бесплатное резюме", callback_data="resume_free")
            ]])
        )
        return

    if data == "resume_vip":
        await q.message.reply_text(
            "👑 VIP резюме — премиум услуга\n\n"
            "Включает:\n"
            "• 2 уникальных дизайна (как на образцах)\n"
            "• Профессиональный текст с достижениями\n"
            "• Сайт-визитка в подарок\n"
            "• HR симулятор\n\n"
            "Функция оплаты скоро будет доступна!"
        )
        return

    if data == "hr_simulator":
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия думает...")
        try:
            prompt = "Начни симуляцию собеседования. Представься как HR-менеджер и задай первый вопрос для собеседования, учитывая профессию и опыт клиента. После каждого ответа давай краткую обратную связь и задавай следующий вопрос."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "analyze_company":
        await q.message.reply_text(
            "📊 Анализ компании\n\n"
            "Напишите название компании или ссылку на вакансию — я соберу всю информацию из открытых источников:\n"
            "• Отзывы сотрудников\n"
            "• Финансовое состояние\n"
            "• Репутация на рынке\n"
            "• Советы по собеседованию"
        )
        return

    if data == "website":
        await q.message.reply_text(
            "🌐 Сайт-визитка (платная услуга)\n\n"
            "3 варианта дизайна на выбор:\n"
            "• Минимализм\n"
            "• Тёмный стиль\n"
            "• Современный\n\n"
            "Функция оплаты скоро будет доступна!"
        )
        return

    if data == "find_courses":
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия думает...")
        try:
            prompt = "Подбери 5 конкретных онлайн-курсов со ссылками для клиента, учитывая его профессию, опыт и цель. Укажи платформу, название курса и примерную стоимость."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "ask_anastasia":
        await q.message.reply_text(
            "Я слушаю вас! Напишите свой вопрос или расскажите о своей ситуации — "
            "постараюсь помочь 😊"
        )
        return


async def voice_handler(update: Update, context):
    user_id = update.effective_user.id
    await update.message.reply_text("Слушаю... распознаю речь 🎤")
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        text = await transcribe_voice(tmp_path)
        os.unlink(tmp_path)
        if not text or not text.strip():
            await update.message.reply_text("Не удалось распознать. Попробуйте ещё раз.")
            return
        await update.message.reply_text("Вы сказали: " + text)

        if user_id in PROFILE_STATE:
            fake_message = update.message
            fake_message._text = text
            await process_text_input(fake_message, user_id, update.effective_user.username or "", text)
            return

        keywords = ["вакансии", "найди работу", "покажи вакансии"]
        if any(k in text.lower() for k in keywords):
            profile = get_user(user_id)
            if profile and profile.get("profile_complete"):
                await update.message.reply_text("Ищу вакансии...")
                vacancies = search_all_vacancies(profile)
                result = format_vacancies(vacancies, profile)
                await update.message.reply_text(result, disable_web_page_preview=True)
                return

        profile = get_user(user_id)
        await update.message.reply_text("Анастасия думает...")
        reply = ask_gpt(user_id, text, profile)
        await update.message.reply_text(reply)
    except Exception as e:
        print("VOICE ERROR:", str(e))
        await update.message.reply_text("Ошибка. Попробуйте написать текстом.")


async def process_text_input(message, user_id, username, text):
    if user_id in PROFILE_STATE:
        step = PROFILE_STATE[user_id]
        PROFILE_DATA[user_id][step] = text

        idx = PROFILE_STEPS.index(step)
        if idx + 1 < len(PROFILE_STEPS):
            next_step = PROFILE_STEPS[idx + 1]
            PROFILE_STATE[user_id] = next_step
            await send_next_question(message, user_id, next_step, PROFILE_DATA[user_id])
        else:
            del PROFILE_STATE[user_id]
            await finish_profile(message, user_id, username, PROFILE_DATA[user_id])
            del PROFILE_DATA[user_id]
        return

    keywords_jobs = ["вакансии", "найди работу", "покажи вакансии"]
    if any(k in text.lower() for k in keywords_jobs):
        profile = get_user(user_id)
        if profile and profile.get("profile_complete"):
            await message.reply_text("Ищу вакансии...")
            vacancies = search_all_vacancies(profile)
            result = format_vacancies(vacancies, profile)
            await message.reply_text(result, disable_web_page_preview=True)
            return

    profile = get_user(user_id)
    await message.reply_text("Анастасия думает...")
    try:
        reply = ask_gpt(user_id, text, profile)
        await message.reply_text(reply)
    except Exception as e:
        print("GPT ERROR:", str(e))
        await message.reply_text("Произошла ошибка. Попробуйте ещё раз.")


async def chat_handler(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    text = update.message.text
    await process_text_input(update.message, user_id, username, text)


def main():
    init_db()
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    print("HEALTH SERVER RUNNING ON PORT " + str(PORT))
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
