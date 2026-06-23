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
- Когда пользователь просит найти вакансии - скажи что ищешь и предложи нажать кнопку поиска
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
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0")
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
                usage_count = COALESCE(users.usage_count, 0) + 1,
                updated_at = NOW()
        """, (user_id,))
        # Add column if not exists
        try:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
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


def search_hh(query, location="", experience="", count=5):
    try:
        params = {
            "text": query,
            "per_page": count,
            "order_by": "relevance",
        }
        if location:
            params["area"] = get_hh_area_id(location)
        if experience:
            params["experience"] = map_experience(experience)

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
        "екатеринбург": "3",
        "новосибирск": "4",
        "казань": "88",
        "нижний новгород": "66",
        "челябинск": "104",
        "самара": "78",
        "уфа": "99",
        "ростов-на-дону": "76",
        "краснодар": "53",
        "воронеж": "26",
        "пермь": "72",
        "волгоград": "24",
    }
    loc = location.lower().strip()
    for key, val in city_map.items():
        if key in loc:
            return val
    return "113"


def map_experience(exp_text):
    exp = str(exp_text).lower()
    if "без опыта" in exp or "0" in exp:
        return "noExperience"
    try:
        years = int(''.join(filter(str.isdigit, exp.split()[0])))
        if years < 1:
            return "noExperience"
        elif years <= 3:
            return "between1And3"
        elif years <= 6:
            return "between3And6"
        else:
            return "moreThan6"
    except:
        return "between3And6"


def search_superjob(query, location="", count=5):
    try:
        params = {
            "keyword": query,
            "count": count,
        }
        if location:
            params["town"] = location

        r = httpx.get(
            "https://api.superjob.ru/2.0/vacancies/",
            params=params,
            headers={
                "X-Api-App-Id": "v3.r.137846771.abb5f1e79b4c7dbbb7c9f6fa285d0a10a01f2ea1.49b08da372ef26b7e3f36a7e87e72e804e63c762",
                "User-Agent": "CareerBot/1.0"
            },
            timeout=10
        )
        data = r.json()
        results = []
        for item in data.get("objects", []):
            salary = ""
            if item.get("payment_from") and item.get("payment_to"):
                salary = str(item["payment_from"]) + "-" + str(item["payment_to"]) + " руб"
            elif item.get("payment_from"):
                salary = "от " + str(item["payment_from"]) + " руб"
            elif item.get("payment_to"):
                salary = "до " + str(item["payment_to"]) + " руб"

            results.append({
                "title": item.get("profession", ""),
                "company": item.get("firm_name", ""),
                "salary": salary,
                "url": item.get("link", ""),
                "source": "superjob.ru"
            })
        return results
    except Exception as e:
        print("SUPERJOB ERROR:", str(e))
        return []


def search_trudvsem(query, location="", count=5):
    try:
        params = {
            "text": query,
            "limit": count,
        }
        if location:
            params["region"] = location

        r = httpx.get(
            "https://trudvsem.ru/api/v1/vacancies",
            params=params,
            headers={"User-Agent": "CareerBot/1.0"},
            timeout=10
        )
        data = r.json()
        results = []
        vacancies = data.get("results", {}).get("vacancies", [])
        for item in vacancies:
            v = item.get("vacancy", {})
            salary = ""
            if v.get("salary_min") and v.get("salary_max"):
                salary = str(v["salary_min"]) + "-" + str(v["salary_max"]) + " руб"
            elif v.get("salary_min"):
                salary = "от " + str(v["salary_min"]) + " руб"

            results.append({
                "title": v.get("job-name", ""),
                "company": v.get("company", {}).get("name", ""),
                "salary": salary,
                "url": "https://trudvsem.ru/vacancy/card/" + str(v.get("id", "")),
                "source": "trudvsem.ru"
            })
        return results
    except Exception as e:
        print("TRUDVSEM ERROR:", str(e))
        return []


def search_all_vacancies(profile):
    query = profile.get("field", "") or profile.get("experience", "") or "менеджер"
    location = profile.get("location", "")
    experience = profile.get("experience", "")

    hh_results = search_hh(query, location, experience, count=5)
    sj_results = search_superjob(query, location, count=3)
    tv_results = search_trudvsem(query, location, count=3)

    all_results = hh_results + sj_results + tv_results
    return all_results


def format_vacancies(vacancies, profile):
    if not vacancies:
        return "К сожалению, по вашему запросу ничего не найдено. Попробуйте изменить параметры поиска."

    name = profile.get("name", "") if profile else ""
    text = ""
    if name:
        text = name + ", вот что я нашла для вас:\n\n"
    else:
        text = "Вот что я нашла:\n\n"

    for i, v in enumerate(vacancies[:10], 1):
        text += str(i) + ". " + v["title"] + "\n"
        text += "   Компания: " + v["company"] + "\n"
        if v["salary"]:
            text += "   Зарплата: " + v["salary"] + "\n"
        text += "   Источник: " + v["source"] + "\n"
        text += "   " + v["url"] + "\n\n"

    text += "Хотите подготовить резюме под конкретную вакансию? Просто пришлите ссылку!"
    return text


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


def get_main_keyboard(has_profile=False):
    keyboard = [
        [InlineKeyboardButton("📄 Резюме", callback_data="resume"),
         InlineKeyboardButton("💼 Найти работу", callback_data="job")],
        [InlineKeyboardButton("🎯 Карьерная стратегия", callback_data="strategy"),
         InlineKeyboardButton("🎤 Подготовка к интервью", callback_data="interview")],
        [InlineKeyboardButton("🔄 Сменить профессию", callback_data="career_change"),
         InlineKeyboardButton("📊 Анализ навыков", callback_data="skills")],
        [InlineKeyboardButton("🔍 Найти вакансии", callback_data="search_jobs")],
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
            "Пишите текстом или отправляйте голосовые сообщения!\n\n"
            "Выберите с чего начнём:"
        )

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(has_profile=bool(profile and profile.get("name")))
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


async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""

    if q.data == "fill_profile":
        PROFILE_STATE[user_id] = "name"
        PROFILE_DATA[user_id] = {}
        await q.message.reply_text(
            "Отлично! Заполним ваш профиль — займёт 1 минуту.\n\nКак вас зовут?"
        )
        return

    if q.data == "search_jobs":
        profile = get_user(user_id)
        if not profile or not profile.get("field"):
            await q.message.reply_text(
                "Для поиска вакансий нужен ваш профиль.\n"
                "Сначала заполните его через кнопку 'Заполнить профиль'."
            )
            return
        await q.message.reply_text(
            "Ищу вакансии на hh.ru, SuperJob и Труд Всем по вашему профилю..."
        )
        vacancies = search_all_vacancies(profile)
        text = format_vacancies(vacancies, profile)
        await q.message.reply_text(text, disable_web_page_preview=True)
        return

    if q.data == "show_profile":
        profile = get_user(user_id)
        if not profile:
            await q.message.reply_text("Профиль не найден. Заполните его через меню.")
            return
        history = get_history(user_id)
        text = "👤 Ваш профиль:\n\n"
        text += "Имя: " + str(profile.get("name") or "—") + "\n"
        text += "Возраст: " + str(profile.get("age") or "—") + "\n"
        text += "Опыт: " + str(profile.get("experience") or "—") + "\n"
        text += "Сфера: " + str(profile.get("field") or "—") + "\n"
        text += "Цель: " + str(profile.get("goal") or "—") + "\n"
        text += "Город: " + str(profile.get("location") or "—") + "\n"
        text += "Обращений: " + str(profile.get("usage_count") or 0) + "\n"
        text += "Сообщений в памяти: " + str(len(history)) + "\n"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Найти вакансии", callback_data="search_jobs")],
            [InlineKeyboardButton("✏️ Обновить профиль", callback_data="fill_profile")],
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ])
        await q.message.reply_text(text, reply_markup=keyboard)
        return

    if q.data == "clear_history":
        clear_history(user_id)
        await q.message.reply_text("История диалога очищена.")
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


async def voice_handler(update: Update, context):
    user_id = update.effective_user.id
    await update.message.reply_text("Слушаю... распознаю речь")
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        text = await transcribe_voice(tmp_path)
        os.unlink(tmp_path)
        if not text or not text.strip():
            await update.message.reply_text("Не удалось распознать речь. Попробуйте ещё раз.")
            return
        await update.message.reply_text("Вы сказали: " + text)

        keywords = ["вакансии", "работу", "найди работу", "покажи вакансии", "ссылки на вакансии"]
        if any(k in text.lower() for k in keywords):
            profile = get_user(user_id)
            if profile and profile.get("field"):
                await update.message.reply_text("Ищу вакансии по вашему профилю...")
                vacancies = search_all_vacancies(profile)
                result = format_vacancies(vacancies, profile)
                await update.message.reply_text(result, disable_web_page_preview=True)
                return

        await update.message.reply_text("Анастасия думает...")
        profile = get_user(user_id)
        reply = ask_gpt(user_id, text, profile)
        await update.message.reply_text(reply)
    except Exception as e:
        print("VOICE ERROR:", str(e))
        await update.message.reply_text("Ошибка при обработке голосового. Попробуйте написать текстом.")


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
            await update.message.reply_text("Сколько лет вы работаете и в какой сфере?")
            return
        if step == "experience":
            PROFILE_DATA[user_id]["experience"] = text
            PROFILE_STATE[user_id] = "field"
            await update.message.reply_text("В какой сфере вы работаете или хотите работать?")
            return
        if step == "field":
            PROFILE_DATA[user_id]["field"] = text
            PROFILE_STATE[user_id] = "goal"
            await update.message.reply_text(
                "Какая ваша главная карьерная цель?\n"
                "(найти работу, повышение, смена профессии, свой бизнес)"
            )
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
            del PROFILE_DATA[user_id]
            await update.message.reply_text(
                "Профиль сохранён! Теперь я смогу давать персональные советы и искать вакансии под вас.\n\nЧем займёмся?",
                reply_markup=get_main_keyboard(has_profile=True)
            )
            return

    keywords = ["вакансии", "найди работу", "покажи вакансии", "ссылки на вакансии", "найти работу"]
    if any(k in text.lower() for k in keywords):
        profile = get_user(user_id)
        if profile and profile.get("field"):
            await update.message.reply_text("Ищу вакансии на hh.ru, SuperJob и Труд Всем...")
            vacancies = search_all_vacancies(profile)
            result = format_vacancies(vacancies, profile)
            await update.message.reply_text(result, disable_web_page_preview=True)
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
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
