import os
import logging
import threading
import json
import httpx
import tempfile
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
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
RATE_LIMIT = {}

# Регистрируем шрифт с поддержкой кириллицы
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

QUESTIONS = [
    {
        "key": "language",
        "text": "Привет! Я Анастасия — ваш персональный карьерный консультант 🤝\n\nЯ рядом, я помогу. Помогу вам зарабатывать больше!\n\nНа каком языке вам удобнее общаться?",
        "keyboard": [["RU Русский", "EN English", "ZH 中文"]]
    },
    {
        "key": "personal",
        "text": (
            "Шаг 1 из 8 — Личные данные\n\n"
            "Пожалуйста, напишите:\n"
            "• ФИО полностью\n"
            "• Дата и место рождения\n"
            "• Город проживания\n"
            "• Гражданство\n"
            "• Семейное положение\n\n"
            "Пример:\n"
            "Иванов Иван Иванович\n"
            "15.05.1990, г. Москва\n"
            "Проживаю: Москва\n"
            "Гражданство: РФ\n"
            "Женат, 2 детей"
        )
    },
    {
        "key": "career",
        "text": (
            "Шаг 2 из 8 — Карьера\n\n"
            "Опишите вашу карьеру по годам (как в трудовой книжке) и текущую ситуацию:\n\n"
            "Пример:\n"
            "2015-2018 — Менеджер по продажам, ООО ТехноПрофи\n"
            "2018-2022 — Руководитель отдела, ООО МегаТрейд\n"
            "2022-н.в. — Директор по продажам, ООО Альфа\n\n"
            "Сфера: оптовая торговля\n"
            "Общий опыт: 9 лет\n"
            "Сейчас: работаю / в поиске / не работаю\n"
            "Причина ухода с последнего места: (если актуально)"
        )
    },
    {
        "key": "target",
        "text": (
            "Шаг 3 из 8 — Цель\n\n"
            "Что вы ищете?\n\n"
            "Пример:\n"
            "Должность: Коммерческий директор\n"
            "Зарплата: от 200 000 руб\n"
            "Формат: офис или гибрид\n"
            "Занятость: полная\n"
            "Переезд: не готов\n"
            "Командировки: до 30% времени"
        )
    },
    {
        "key": "education",
        "text": (
            "Шаг 4 из 8 — Образование и навыки\n\n"
            "Пример:\n"
            "Образование: Высшее, МГУ, менеджмент, 2012\n\n"
            "Курсы: Skillbox — Управление продажами 2021,\n"
            "Coursera — Leadership 2022\n\n"
            "Навыки: CRM (Bitrix24, AmoCRM), B2B продажи,\n"
            "переговоры, управление командой 15 чел,\n"
            "бюджетирование, Excel продвинутый\n\n"
            "Сертификаты: если есть"
        )
    },
    {
        "key": "achievements",
        "text": (
            "Шаг 5 из 8 — Достижения\n\n"
            "Ваши главные достижения (желательно в цифрах):\n\n"
            "Пример:\n"
            "• Увеличил объём продаж на 40% за год\n"
            "• Привлёк 50 новых корпоративных клиентов\n"
            "• Сократил дебиторскую задолженность на 25%\n"
            "• Открыл 3 новых региональных филиала\n"
            "• Вывел продукт на рынок за 6 месяцев\n\n"
            "Если достижений нет — напишите: нет"
        )
    },
    {
        "key": "additional",
        "text": (
            "Шаг 6 из 8 — Дополнительно\n\n"
            "Пример:\n"
            "Языки: Русский — родной, Английский — B2\n"
            "Водительские права: кат. B, личный автомобиль\n"
            "Готов к командировкам: да\n"
            "Ограничения по здоровью: нет\n"
            "Судимости: нет\n"
            "Язык резюме: русский"
        )
    },
    {
        "key": "personal_info",
        "text": (
            "Шаг 7 из 8 — О себе\n\n"
            "Пример:\n"
            "Хобби: спорт, путешествия, чтение бизнес-литературы\n\n"
            "Личные качества: целеустремлённый, ответственный,\n"
            "стрессоустойчивый, лидер по натуре\n\n"
            "Контакты для резюме:\n"
            "Телефон: +7 999 123-45-67\n"
            "Email: ivanov@mail.ru\n"
            "Telegram: @ivanov"
        )
    },
    {
        "key": "photo",
        "text": "Шаг 8 из 8 — Фото\n\nЕсть фото для резюме?\n\nФото повышает шансы на отклик на 30%!",
        "keyboard": [["📸 Загружу фото", "❌ Без фото"]]
    },
]


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
        return False


def get_history(user_id):
    history = redis_get("history:" + str(user_id))
    return history if history else []


def save_history(user_id, history):
    if len(history) > 10:
        history = history[-10:]
    redis_set("history:" + str(user_id), history, ttl=604800)


def clear_history(user_id):
    redis_delete("history:" + str(user_id))


def check_rate_limit(user_id):
    now = time.time()
    if user_id not in RATE_LIMIT:
        RATE_LIMIT[user_id] = []
    RATE_LIMIT[user_id] = [t for t in RATE_LIMIT[user_id] if now - t < 60]
    if len(RATE_LIMIT[user_id]) >= 10:
        return False
    RATE_LIMIT[user_id].append(now)
    return True


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
                phone TEXT,
                language TEXT DEFAULT 'ru',
                personal TEXT,
                career TEXT,
                target TEXT,
                education TEXT,
                achievements TEXT,
                additional TEXT,
                personal_info TEXT,
                photo TEXT,
                plan TEXT DEFAULT 'free',
                free_resume_used BOOLEAN DEFAULT FALSE,
                usage_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE,
                profile_complete BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cols = [
            ("phone", "TEXT"),
            ("free_resume_used", "BOOLEAN DEFAULT FALSE"),
            ("is_blocked", "BOOLEAN DEFAULT FALSE"),
            ("profile_complete", "BOOLEAN DEFAULT FALSE"),
            ("usage_count", "INTEGER DEFAULT 0"),
            ("personal", "TEXT"),
            ("career", "TEXT"),
            ("target", "TEXT"),
            ("education", "TEXT"),
            ("achievements", "TEXT"),
            ("additional", "TEXT"),
            ("personal_info", "TEXT"),
            ("photo", "TEXT"),
            ("language", "TEXT DEFAULT 'ru'"),
        ]
        for col, col_type in cols:
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


def save_full_profile(user_id, username, data):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, language, personal, career, target,
                education, achievements, additional, personal_info, photo, profile_complete)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (user_id) DO UPDATE SET
                language = EXCLUDED.language,
                personal = EXCLUDED.personal,
                career = EXCLUDED.career,
                target = EXCLUDED.target,
                education = EXCLUDED.education,
                achievements = EXCLUDED.achievements,
                additional = EXCLUDED.additional,
                personal_info = EXCLUDED.personal_info,
                photo = EXCLUDED.photo,
                profile_complete = TRUE,
                updated_at = NOW()
        """, (
            user_id, username,
            data.get("language", "ru"),
            data.get("personal"), data.get("career"),
            data.get("target"), data.get("education"),
            data.get("achievements"), data.get("additional"),
            data.get("personal_info"), data.get("photo"),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("SAVE PROFILE ERROR:", str(e))


def mark_free_resume_used(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET free_resume_used = TRUE, updated_at = NOW() WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("MARK RESUME ERROR:", str(e))


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
        pass


def delete_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass


def draw_text_wrapped(c, text, x, y, max_width, font_name, font_size, line_height):
    c.setFont(font_name, font_size)
    words = text.split()
    line = ""
    for word in words:
        test_line = line + " " + word if line else word
        if c.stringWidth(test_line, font_name, font_size) <= max_width:
            line = test_line
        else:
            if line:
                c.drawString(x, y, line)
                y -= line_height
            line = word
    if line:
        c.drawString(x, y, line)
        y -= line_height
    return y


def generate_resume_pdf(profile, gpt_resume_text):
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        FONT = "STSong-Light"
        FONT_BOLD = "STSong-Light"
        c = canvas.Canvas(tmp_path, pagesize=A4)
        width, height = A4
        margin_left = 50
        margin_right = 40
        content_width = width - margin_left - margin_right

        # Белый фон (hh.ru стиль)
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, width, height, fill=1, stroke=0)

        # Верхняя полоска - красная как hh.ru
        c.setFillColorRGB(0.87, 0.13, 0.13)
        c.rect(0, height - 8, width, 8, fill=1, stroke=0)

        personal = profile.get("personal", "")
        name_line = personal.split("\n")[0].strip() if personal else "Резюме"

        # Имя крупно
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(FONT_BOLD, 22)
        c.drawString(margin_left, height - 45, name_line[:55])

        # Тонкая линия под именем
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.5)
        c.line(margin_left, height - 55, width - margin_right, height - 55)

        y = height - 75
        line_height = 15

        lines = gpt_resume_text.split("\n")

        for line in lines:
            if y < 50:
                c.showPage()
                # Белый фон на новой странице
                c.setFillColorRGB(1, 1, 1)
                c.rect(0, 0, width, height, fill=1, stroke=0)
                c.setFillColorRGB(0.87, 0.13, 0.13)
                c.rect(0, height - 8, width, 8, fill=1, stroke=0)
                y = height - 30
                c.setFillColorRGB(0.1, 0.1, 0.1)

            line = line.strip()
            if not line:
                y -= 6
                continue

            is_section = (
                line.isupper() and len(line) > 2 or
                (line.endswith(":") and len(line) < 40 and line[0].isupper())
            )

            if is_section:
                y -= 8
                # Заголовок раздела - серый текст как на hh
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.setFont(FONT_BOLD, 9)
                clean = line.replace(":", "").strip().upper()
                c.drawString(margin_left, y, clean[:60])
                y -= 4
                # Линия под заголовком
                c.setStrokeColorRGB(0.87, 0.13, 0.13)
                c.setLineWidth(1.5)
                c.line(margin_left, y, width - margin_right, y)
                c.setLineWidth(0.5)
                y -= line_height
                c.setFillColorRGB(0.1, 0.1, 0.1)
            else:
                c.setFont(FONT, 10)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                clean = line.replace("**", "").replace("•", "—")
                # Если начинается с тире или дефиса — отступ
                if clean.startswith("-") or clean.startswith("—"):
                    y = draw_text_wrapped(c, clean, margin_left + 10, y, content_width - 10, FONT, 10, line_height)
                else:
                    y = draw_text_wrapped(c, clean, margin_left, y, content_width, FONT, 10, line_height)

        # Футер
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.line(margin_left, 35, width - margin_right, 35)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.setFont(FONT, 7)
        c.drawCentredString(width / 2, 22, "Резюме создано с помощью AI Career Bot Анастасия")

        c.save()
        return tmp_path

    except Exception as e:
        print("PDF ERROR:", str(e))
        return None


def build_resume_prompt(profile):
    return f"""
Создай профессиональное резюме на основе данных клиента.
Язык резюме: определи из поля "additional" (язык резюме).

ДАННЫЕ КЛИЕНТА:

ЛИЧНЫЕ ДАННЫЕ:
{profile.get('personal', '')}

КАРЬЕРА:
{profile.get('career', '')}

ЦЕЛЬ:
{profile.get('target', '')}

ОБРАЗОВАНИЕ И НАВЫКИ:
{profile.get('education', '')}

ДОСТИЖЕНИЯ:
{profile.get('achievements', '')}

ДОПОЛНИТЕЛЬНО:
{profile.get('additional', '')}

О СЕБЕ:
{profile.get('personal_info', '')}

ТРЕБОВАНИЯ К РЕЗЮМЕ:
1. Структура: ФИО И КОНТАКТЫ → ЦЕЛЬ → ОПЫТ РАБОТЫ → ОБРАЗОВАНИЕ → НАВЫКИ → ДОСТИЖЕНИЯ → О СЕБЕ → ДОПОЛНИТЕЛЬНО
2. Каждый раздел начинай с ЗАГЛАВНЫХ БУКВ без двоеточия
3. Опыт работы — по годам в обратном хронологическом порядке
4. Достижения — с цифрами и фактами
5. Профессиональный деловой стиль без лишних слов
6. Адаптируй под уровень опыта
7. НЕ используй markdown символы * # и т.д.
"""


def build_system_prompt(profile):
    lang_map = {
        "RU Русский": "русском",
        "EN English": "English only",
        "ZH 中文": "中文"
    }
    lang = profile.get("language", "RU Русский") if profile else "RU Русский"
    lang_instruction = lang_map.get(lang, "русском")

    base = f"""
Ты - Анастасия, опытный AI карьерный консультант.
Ты — диагност, консультант, подруга, психолог и профессионал.
Принцип: не продавать — выявлять потребности и помогать через заботу.
Лозунг: "Я рядом, я помогу. Помогу тебе зарабатывать больше."

КРИТИЧЕСКИ ВАЖНО: отвечай СТРОГО на {lang_instruction}. НИКОГДА не смешивай языки!

Стиль: тёплый, живой, конкретный. Один вопрос за раз.
Никогда не говори "я не могу" — всегда предлагай решение.
Если человек тревожится — сначала поддержи, потом советуй.
"""
    if not profile:
        return base

    extra = "\n\nПРОФИЛЬ КЛИЕНТА:\n"
    if profile.get("personal"):
        extra += "Личные данные: " + str(profile["personal"])[:200] + "\n"
    if profile.get("career"):
        extra += "Карьера: " + str(profile["career"])[:300] + "\n"
    if profile.get("target"):
        extra += "Цель: " + str(profile["target"])[:200] + "\n"
    if profile.get("education"):
        extra += "Образование: " + str(profile["education"])[:200] + "\n"
    if profile.get("achievements"):
        extra += "Достижения: " + str(profile["achievements"])[:200] + "\n"

    return base + extra


def ask_gpt(user_id, user_message, profile=None):
    history = get_history(user_id)
    history.append({"role": "user", "content": user_message})
    system = build_system_prompt(profile)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + history,
        max_tokens=1000,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    save_history(user_id, history)
    increment_usage(user_id)
    return reply


async def transcribe_voice(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, language="ru"
        )
    return transcript.text


def get_main_keyboard(profile=None):
    keyboard = [
        [InlineKeyboardButton("📄 Бесплатное резюме", callback_data="resume_free"),
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


async def send_question(message, step_index, profile_data):
    if step_index >= len(QUESTIONS):
        return
    q = QUESTIONS[step_index]
    text = q["text"]
    keyboard = q.get("keyboard")
    if keyboard:
        await message.reply_text(text, reply_markup=make_keyboard(keyboard))
    else:
        await message.reply_text(text)


async def finish_profile(message, user_id, username, data):
    save_full_profile(user_id, username, data)
    clear_history(user_id)
    profile = get_user(user_id)

    personal = data.get("personal", "")
    name = personal.split("\n")[0] if personal else "друг"
    career = data.get("career", "").lower()
    has_experience = not any(w in career for w in ["нет опыта", "без опыта", "начинающий"])

    if has_experience:
        summary = (
            name + ", профиль заполнен! 🎉\n\n"
            "Отличный опыт! Теперь я знаю всё необходимое.\n\n"
            "Начнём с бесплатного резюме — это займёт минуту.\n"
            "Потом предложу варианты как сделать его ещё сильнее!"
        )
    else:
        summary = (
            name + ", профиль заполнен! 🎉\n\n"
            "Отличный старт! Отсутствие опыта — не проблема.\n"
            "Создам резюме которое выгодно представит ваши навыки!\n\n"
            "Начнём с бесплатного резюме прямо сейчас?"
        )

    await message.reply_text(summary, reply_markup=get_main_keyboard(profile))


async def start(update: Update, context):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "друг"
    profile = get_user(user_id)

    if profile and profile.get("is_blocked"):
        await update.message.reply_text("Ваш аккаунт заблокирован. Обратитесь в поддержку.")
        return

    if profile and profile.get("profile_complete"):
        name = profile.get("personal", "").split("\n")[0] if profile.get("personal") else first_name
        await update.message.reply_text(
            "С возвращением, " + name + "! Чем могу помочь сегодня? 😊",
            reply_markup=get_main_keyboard(profile)
        )
    else:
        PROFILE_STATE[user_id] = 0
        PROFILE_DATA[user_id] = {}
        q = QUESTIONS[0]
        await update.message.reply_text(q["text"], reply_markup=make_keyboard(q["keyboard"]))


async def reset_cmd(update: Update, context):
    user_id = update.effective_user.id
    delete_user(user_id)
    clear_history(user_id)
    if user_id in PROFILE_STATE:
        del PROFILE_STATE[user_id]
    if user_id in PROFILE_DATA:
        del PROFILE_DATA[user_id]
    await update.message.reply_text("Профиль удалён. Напишите /start чтобы начать заново.")


async def callback_handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""
    data = q.data

    if data.startswith("ans_") and user_id in PROFILE_STATE:
        answer = data[4:]
        step_index = PROFILE_STATE[user_id]
        key = QUESTIONS[step_index]["key"]
        PROFILE_DATA[user_id][key] = answer
        next_index = step_index + 1
        if next_index < len(QUESTIONS):
            PROFILE_STATE[user_id] = next_index
            await send_question(q.message, next_index, PROFILE_DATA[user_id])
        else:
            del PROFILE_STATE[user_id]
            await finish_profile(q.message, user_id, username, PROFILE_DATA[user_id])
            del PROFILE_DATA[user_id]
        return

    if data == "start_profile":
        PROFILE_STATE[user_id] = 0
        PROFILE_DATA[user_id] = {}
        q2 = QUESTIONS[0]
        await q.message.reply_text(q2["text"], reply_markup=make_keyboard(q2["keyboard"]))
        return

    if data == "resume_free":
        profile = get_user(user_id)
        if not profile or not profile.get("profile_complete"):
            await q.message.reply_text(
                "Сначала заполните профиль — это займёт 3 минуты!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")
                ]])
            )
            return

        if profile.get("free_resume_used"):
            await q.message.reply_text(
                "Вы уже использовали бесплатное резюме 📄\n\n"
                "Хотите улучшить его?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ ПРО резюме", callback_data="resume_pro")],
                    [InlineKeyboardButton("👑 VIP резюме", callback_data="resume_vip")],
                ])
            )
            return

        await q.message.reply_text("Анастасия создаёт ваше резюме... ⏳\n\nЭто займёт 30-60 секунд.")

        try:
            prompt = build_resume_prompt(profile)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты профессиональный составитель резюме. Создавай структурированные профессиональные резюме. НЕ используй markdown символы * # и т.д."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
            )
            resume_text = response.choices[0].message.content
            pdf_path = generate_resume_pdf(profile, resume_text)

            if pdf_path:
                with open(pdf_path, "rb") as pdf_file:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=pdf_file,
                        filename="resume_anastasia.pdf",
                        caption="📄 Ваше резюме готово!\n\nСоздано AI Career Bot — Анастасия"
                    )
                os.unlink(pdf_path)
                mark_free_resume_used(user_id)
                await q.message.reply_text(
                    "Резюме готово! 🎉\n\n"
                    "Анастасия заботится о вас и хочет предложить больше:\n\n"
                    "⭐ ПРО резюме — ATS-оптимизация + 2 дизайна\n"
                    "👑 VIP резюме — премиум дизайн\n"
                    "🔍 Найти вакансии под ваш профиль\n"
                    "🎤 HR симулятор — подготовка к собеседованию",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⭐ ПРО резюме", callback_data="resume_pro"),
                         InlineKeyboardButton("🔍 Вакансии", callback_data="search_jobs")],
                        [InlineKeyboardButton("🎤 HR симулятор", callback_data="hr_simulator"),
                         InlineKeyboardButton("👑 VIP резюме", callback_data="resume_vip")],
                    ])
                )
            else:
                await q.message.reply_text(resume_text)
                mark_free_resume_used(user_id)

        except Exception as e:
            print("RESUME ERROR:", str(e))
            await q.message.reply_text("Произошла ошибка. Попробуйте ещё раз.")
        return

    if data in ["resume_pro", "resume_vip", "website"]:
        names = {"resume_pro": "ПРО резюме", "resume_vip": "VIP резюме", "website": "Сайт-визитка"}
        await q.message.reply_text(
            f"💼 {names[data]} — платная услуга\n\n"
            "Функция оплаты скоро будет доступна!\n"
            "Мы уведомим вас когда это произойдёт.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📄 Бесплатное резюме", callback_data="resume_free")
            ]])
        )
        return

    if data == "search_jobs":
        profile = get_user(user_id)
        if not profile or not profile.get("profile_complete"):
            await q.message.reply_text(
                "Для поиска вакансий нужен ваш профиль.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")
                ]])
            )
            return
        await q.message.reply_text("Ищу вакансии по вашему профилю... 🔍")
        try:
            target = profile.get("target", "")
            career = profile.get("career", "")
            personal = profile.get("personal", "")
            city = "Москва"
            for line in personal.split("\n"):
                if "проживаю" in line.lower() or "город" in line.lower():
                    city = line.split(":")[-1].strip()
                    break

            query = ""
            for line in target.split("\n"):
                if "должность" in line.lower():
                    query = line.split(":")[-1].strip()
                    break
            if not query:
                query = career.split("\n")[-1].strip()[:50]

            area_id = "113"
            city_map = {"москва": "1", "спб": "2", "питер": "2", "екатеринбург": "3",
                       "новосибирск": "4", "казань": "88"}
            for key, val in city_map.items():
                if key in city.lower():
                    area_id = val
                    break

            params = {"text": query, "per_page": 8, "area": area_id}
            r = httpx.get("https://api.hh.ru/vacancies", params=params,
                         headers={"User-Agent": "CareerBot/1.0"}, timeout=10)
            items = r.json().get("items", [])

            if not items:
                await q.message.reply_text("По вашему запросу ничего не найдено.")
                return

            personal_name = personal.split("\n")[0] if personal else ""
            text = personal_name + ", вот что я нашла:\n\n"
            for i, item in enumerate(items[:8], 1):
                salary = ""
                if item.get("salary"):
                    s = item["salary"]
                    if s.get("from"):
                        salary = " | от " + str(s["from"]) + " " + str(s.get("currency", ""))
                text += str(i) + ". " + item.get("name", "") + "\n"
                text += "   🏢 " + item.get("employer", {}).get("name", "") + salary + "\n"
                text += "   🔗 " + item.get("alternate_url", "") + "\n\n"

            text += "Хотите подготовить резюме под конкретную вакансию?"
            await q.message.reply_text(text, disable_web_page_preview=True)
        except Exception as e:
            print("SEARCH ERROR:", str(e))
            await q.message.reply_text("Ошибка поиска. Попробуйте позже.")
        return

    if data == "hr_simulator":
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия думает... 🎤")
        try:
            prompt = "Начни симуляцию HR собеседования. Представься как HR-менеджер компании. Задай первый вопрос исходя из профиля кандидата. После каждого ответа давай краткую обратную связь и задавай следующий вопрос."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "analyze_company":
        await q.message.reply_text(
            "📊 Анализ компании\n\n"
            "Напишите название компании — соберу информацию:\n"
            "• Отзывы сотрудников\n"
            "• Репутация на рынке\n"
            "• Советы по собеседованию"
        )
        return

    if data == "find_courses":
        profile = get_user(user_id)
        await q.message.reply_text("Анастасия подбирает курсы... 📚")
        try:
            prompt = "Подбери 5 конкретных онлайн-курсов для клиента исходя из его профиля и целей. Укажи: платформу, название, примерную стоимость и почему этот курс подойдёт."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "ask_anastasia":
        await q.message.reply_text(
            "Я слушаю вас! Напишите вопрос или расскажите о ситуации 😊\n\n"
            "Можете писать текстом или голосовым сообщением 🎤"
        )
        return

    if data == "show_profile":
        profile = get_user(user_id)
        if not profile:
            await q.message.reply_text("Профиль не найден.")
            return
        text = "👤 Ваш профиль:\n\n"
        if profile.get("personal"):
            text += "📋 Личные данные:\n" + str(profile["personal"])[:200] + "\n\n"
        if profile.get("career"):
            text += "💼 Карьера:\n" + str(profile["career"])[:200] + "\n\n"
        if profile.get("target"):
            text += "🎯 Цель:\n" + str(profile["target"])[:150] + "\n\n"
        text += "Обращений: " + str(profile.get("usage_count") or 0)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Обновить профиль", callback_data="start_profile")],
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back_menu")]
        ])
        await q.message.reply_text(text, reply_markup=keyboard)
        return

    if data == "clear_history":
        clear_history(user_id)
        await q.message.reply_text("История очищена. ✅")
        return

    if data == "back_menu":
        profile = get_user(user_id)
        await q.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(profile))
        return


async def voice_handler(update: Update, context):
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("Слишком много сообщений. Подождите минуту.")
        return
    await update.message.reply_text("Слушаю... 🎤")
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        text = await transcribe_voice(tmp_path)
        os.unlink(tmp_path)
        if not text or not text.strip():
            await update.message.reply_text("Не удалось распознать. Попробуйте ещё раз.")
            return
        await update.message.reply_text("Вы сказали: " + text)
        await process_text(update.message, user_id, update.effective_user.username or "", text)
    except Exception as e:
        print("VOICE ERROR:", str(e))
        await update.message.reply_text("Ошибка. Попробуйте написать текстом.")


async def process_text(message, user_id, username, text):
    if user_id in PROFILE_STATE:
        step_index = PROFILE_STATE[user_id]
        key = QUESTIONS[step_index]["key"]
        PROFILE_DATA[user_id][key] = text
        next_index = step_index + 1
        if next_index < len(QUESTIONS):
            PROFILE_STATE[user_id] = next_index
            await send_question(message, next_index, PROFILE_DATA[user_id])
        else:
            del PROFILE_STATE[user_id]
            await finish_profile(message, user_id, username, PROFILE_DATA[user_id])
            del PROFILE_DATA[user_id]
        return

    profile = get_user(user_id)
    await message.reply_text("Анастасия думает... 💭")
    try:
        reply = ask_gpt(user_id, text, profile)
        await message.reply_text(reply)
    except Exception as e:
        print("GPT ERROR:", str(e))
        await message.reply_text("Произошла ошибка. Попробуйте ещё раз.")


async def chat_handler(update: Update, context):
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("Слишком много сообщений. Подождите минуту.")
        return
    await process_text(update.message, user_id, update.effective_user.username or "", update.message.text)


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
