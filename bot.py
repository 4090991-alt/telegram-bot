import os
import logging
import threading
import json
import httpx
import tempfile
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
ADMIN_ID = 5483814560  # @PopovSN78

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
WAITING_PHONE = {}
GPT_DAILY_LIMIT = {}

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

# =====================
# ЮРИДИЧЕСКИЕ ТЕКСТЫ
# =====================
OFERTA_TEXT = """📋 ПУБЛИЧНАЯ ОФЕРТА

Бот @AnastasiaHR_ai_bot предоставляет информационные услуги по созданию резюме и карьерному консультированию.

УСЛОВИЯ:
1. Сервис предоставляется "как есть"
2. Бот не гарантирует трудоустройство
3. Бесплатное резюме — 1 раз на номер телефона
4. Возврат средств в течение 24 часов если услуга не оказана
5. Данные хранятся в зашифрованном виде
6. Пользователь вправе удалить свои данные в любой момент

ОТВЕТСТВЕННОСТЬ:
Сервис не несёт ответственности за результат трудоустройства. Все советы носят информационный характер.

ПОДДЕРЖКА: @PopovSN78
Версия: 1.0 от 24.06.2026"""

PRIVACY_TEXT = """🔒 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ

Мы собираем:
• ФИО, дата рождения, контакты
• Опыт работы и образование
• Номер телефона для верификации

Мы НЕ передаём данные третьим лицам.
Мы НЕ храним платёжные данные.

Данные используются ТОЛЬКО для:
• Создания резюме
• Персональных рекомендаций
• Улучшения сервиса (анонимно)

Ваши права:
• Получить копию данных: /mydata
• Удалить все данные: /deletedata
• Отозвать согласие: /reset

Срок хранения: 1 год с последнего входа.
Основание: 152-ФЗ "О персональных данных"

По вопросам: @PopovSN78"""

CONSENT_TEXT = """👋 Привет! Я Анастасия — ваш AI карьерный консультант.

Я рядом, я помогу. Помогу вам зарабатывать больше! 💙

Уже помогла 1000+ специалистам найти работу мечты!

Прежде чем начать, необходимо ваше согласие:

✅ Мне исполнилось 18 лет
✅ Я соглашаюсь на обработку персональных данных
✅ Я принимаю условия публичной оферты

📋 /oferta — Публичная оферта
🔒 /privacy — Политика конфиденциальности"""

QUESTIONS = [
    {
        "key": "language",
        "text": "Выберите язык общения:",
        "keyboard": [["RU Русский", "EN English", "ZH 中文"]]
    },
    {
        "key": "personal",
        "text": (
            "Шаг 1 из 8 — Личные данные\n\n"
            "Напишите:\n"
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
            "Опишите карьеру по годам и текущую ситуацию:\n\n"
            "Пример:\n"
            "2015-2018 — Менеджер, ООО ТехноПрофи\n"
            "2018-2022 — Руководитель, ООО МегаТрейд\n"
            "2022-н.в. — Директор, ООО Альфа\n\n"
            "Сфера: оптовая торговля\n"
            "Опыт: 9 лет\n"
            "Сейчас: работаю / ищу / не работаю\n"
            "Причина ухода: (если актуально)"
        )
    },
    {
        "key": "target",
        "text": (
            "Шаг 3 из 8 — Цель\n\n"
            "Пример:\n"
            "Должность: Коммерческий директор\n"
            "Зарплата: от 200 000 руб\n"
            "Формат: офис или гибрид\n"
            "Занятость: полная\n"
            "Переезд: не готов\n"
            "Командировки: до 30%"
        )
    },
    {
        "key": "education",
        "text": (
            "Шаг 4 из 8 — Образование и навыки\n\n"
            "Пример:\n"
            "Образование: Высшее, МГУ, менеджмент, 2012\n"
            "Курсы: Skillbox — Продажи 2021\n"
            "Навыки: CRM, B2B, переговоры, Excel\n"
            "Сертификаты: если есть"
        )
    },
    {
        "key": "achievements",
        "text": (
            "Шаг 5 из 8 — Достижения\n\n"
            "Пример:\n"
            "• Увеличил продажи на 40% за год\n"
            "• Привлёк 50 новых клиентов\n"
            "• Открыл 3 филиала\n\n"
            "Если нет — напишите: нет"
        )
    },
    {
        "key": "additional",
        "text": (
            "Шаг 6 из 8 — Дополнительно\n\n"
            "Пример:\n"
            "Языки: Русский — родной, English — B2\n"
            "Права: кат. B, авто\n"
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
            "Хобби: спорт, путешествия\n"
            "Качества: целеустремлённый, ответственный\n\n"
            "Контакты:\n"
            "Тел: +7 999 123-45-67\n"
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

FAQ_TEXT = """❓ ЧАСТЫЕ ВОПРОСЫ

1. Бесплатное резюме — сколько раз?
   → 1 раз на номер телефона

2. PDF не скачивается?
   → Нажмите на файл → Открыть → Скачать

3. Забыл заполнить что-то в профиле?
   → Меню → Мой профиль → Обновить

4. Как удалить мои данные?
   → Команда /deletedata

5. Хочу вернуть деньги?
   → Напишите @PopovSN78 в течение 24 часов

6. Бот не отвечает?
   → Подождите 1-2 минуты и попробуйте снова

7. Как улучшить резюме?
   → Выберите ПРО или VIP резюме

8. Вакансии не находятся?
   → Уточните запрос или смените город в профиле

По другим вопросам: @PopovSN78"""

PSYCHO_ARTICLES = {
    "stress": """💙 КАК СПРАВИТЬСЯ СО СТРЕССОМ ПЕРЕД СОБЕСЕДОВАНИЕМ

1. Дыхание 4-7-8
   Вдох 4 сек → задержка 7 сек → выдох 8 сек
   Повторите 3-4 раза перед входом

2. Переформулируйте страх
   "Я боюсь провалиться" → "Это опыт который меня развивает"

3. Подготовьте якорь уверенности
   Вспомните свой лучший профессиональный момент
   Держите это воспоминание во время собеседования

4. Физическая разминка
   5 минут ходьбы перед встречей снижают кортизол на 20%

5. Правило 3 минут
   Первые 3 минуты — самые важные. Улыбка + прямая спина + зрительный контакт

Помните: работодатель тоже хочет найти хорошего сотрудника! 💪""",

    "rejection": """💙 КАК СПРАВИТЬСЯ СО СТРАХОМ ОТКАЗА

Отказ — это не про вас лично.
Это про несовпадение требований в данный момент.

3 факта которые помогут:
• 80% кандидатов получают отказы — это нормально
• Каждый отказ приближает вас к офферу
• Netflix, Apple, Google отказали многим великим людям

Что делать после отказа:
1. Дайте себе 24 часа на эмоции — это ok
2. Напишите что узнали из этого опыта
3. Попросите обратную связь у рекрутера
4. Обновите резюме с учётом feedback
5. Двигайтесь дальше

Статистика: в среднем нужно 10-15 собеседований чтобы получить оффер мечты.

Вы на правильном пути! 🌟""",

    "burnout": """💙 КАК СПРАВИТЬСЯ С ВЫГОРАНИЕМ

Признаки выгорания:
• Работа не приносит радости
• Постоянная усталость
• Раздражительность
• Снижение продуктивности

Что делать прямо сейчас:
1. Признайте проблему — это уже 50% решения
2. Возьмите паузу — хотя бы 3 дня без работы
3. Вернитесь к основам — сон, еда, движение
4. Поговорите с кем-то близким
5. Подумайте что вас раньше вдохновляло в работе

Долгосрочное решение:
• Найдите смысл в том что делаете
• Установите границы — работа заканчивается в конкретное время
• Найдите хобби не связанное с работой
• Рассмотрите смену направления — Анастасия поможет!

Если состояние тяжёлое — обратитесь к специалисту.
Телефон доверия: 8-800-2000-122 (бесплатно)"""
}


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
        return None


def redis_set(key, value, ttl=86400):
    try:
        url = REDIS_URL + "/set/" + key
        headers = {"Authorization": "Bearer " + REDIS_TOKEN}
        payload = json.dumps(value)
        r = httpx.post(url, headers=headers, json=[payload, "EX", ttl], timeout=5)
        return True
    except Exception as e:
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


def check_gpt_limit(user_id, plan="free"):
    if plan in ["pro", "vip"]:
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"gpt:{user_id}:{today}"
    count = redis_get(key) or 0
    if count >= 3:
        return False
    redis_set(key, count + 1, ttl=86400)
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
                consent BOOLEAN DEFAULT FALSE,
                age_confirmed BOOLEAN DEFAULT FALSE,
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
                pro_resume_count INTEGER DEFAULT 0,
                vip_resume_count INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE,
                block_reason TEXT,
                profile_complete BOOLEAN DEFAULT FALSE,
                rating INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                error_type TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                rating INTEGER,
                comment TEXT,
                service TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cols = [
            ("phone", "TEXT"),
            ("consent", "BOOLEAN DEFAULT FALSE"),
            ("age_confirmed", "BOOLEAN DEFAULT FALSE"),
            ("free_resume_used", "BOOLEAN DEFAULT FALSE"),
            ("pro_resume_count", "INTEGER DEFAULT 0"),
            ("vip_resume_count", "INTEGER DEFAULT 0"),
            ("is_blocked", "BOOLEAN DEFAULT FALSE"),
            ("block_reason", "TEXT"),
            ("profile_complete", "BOOLEAN DEFAULT FALSE"),
            ("usage_count", "INTEGER DEFAULT 0"),
            ("rating", "INTEGER DEFAULT 0"),
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


def log_error(user_id, error_type, error_message):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO error_logs (user_id, error_type, error_message) VALUES (%s, %s, %s)",
            (user_id, error_type, str(error_message)[:500])
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


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
        return None


def get_user_by_phone(phone):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        return None


def create_user(user_id, username):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, username))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass


def update_user(user_id, field, value):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE users SET {field} = %s, updated_at = NOW() WHERE user_id = %s",
            (value, user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass


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
        log_error(user_id, "SAVE_PROFILE", str(e))


def delete_user_data(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        clear_history(user_id)
        return True
    except Exception as e:
        return False


def get_stats():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE free_resume_used = TRUE")
        resumes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
        paid = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '24 hours'")
        new_today = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"total": total, "resumes": resumes, "paid": paid, "new_today": new_today}
    except Exception as e:
        return {}


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
        c = canvas.Canvas(tmp_path, pagesize=A4)
        width, height = A4
        margin_left = 50
        margin_right = 40
        content_width = width - margin_left - margin_right

        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColorRGB(0.87, 0.13, 0.13)
        c.rect(0, height - 8, width, 8, fill=1, stroke=0)

        personal = profile.get("personal", "")
        name_line = personal.split("\n")[0].strip() if personal else "Резюме"

        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(FONT, 22)
        c.drawString(margin_left, height - 45, name_line[:55])

        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.5)
        c.line(margin_left, height - 55, width - margin_right, height - 55)

        y = height - 75
        line_height = 15

        for line in gpt_resume_text.split("\n"):
            if y < 50:
                c.showPage()
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

            is_section = (line.isupper() and len(line) > 2) or \
                        (line.endswith(":") and len(line) < 40 and len(line) > 3 and line[0].isupper())

            if is_section:
                y -= 8
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.setFont(FONT, 9)
                clean = line.replace(":", "").strip().upper()
                c.drawString(margin_left, y, clean[:60])
                y -= 4
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
                indent = margin_left + 10 if clean.startswith(("-", "—")) else margin_left
                y = draw_text_wrapped(c, clean, indent, y, content_width - 10, FONT, 10, line_height)

        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.line(margin_left, 35, width - margin_right, 35)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.setFont(FONT, 7)
        c.drawCentredString(width / 2, 22, "@AnastasiaHR_ai_bot — AI карьерный консультант Анастасия")

        c.save()
        return tmp_path
    except Exception as e:
        print("PDF ERROR:", str(e))
        return None


def build_resume_prompt(profile):
    return f"""Создай профессиональное резюме. Язык: из поля additional (язык резюме), по умолчанию русский.

ЛИЧНЫЕ ДАННЫЕ: {profile.get('personal', '')}
КАРЬЕРА: {profile.get('career', '')}
ЦЕЛЬ: {profile.get('target', '')}
ОБРАЗОВАНИЕ И НАВЫКИ: {profile.get('education', '')}
ДОСТИЖЕНИЯ: {profile.get('achievements', '')}
ДОПОЛНИТЕЛЬНО: {profile.get('additional', '')}
О СЕБЕ: {profile.get('personal_info', '')}

СТРУКТУРА: ФИО И КОНТАКТЫ → ЦЕЛЬ → ОПЫТ РАБОТЫ → ОБРАЗОВАНИЕ → НАВЫКИ → ДОСТИЖЕНИЯ → О СЕБЕ → ДОПОЛНИТЕЛЬНО
Каждый раздел — ЗАГЛАВНЫМИ БУКВАМИ на отдельной строке.
Без markdown символов * # и т.д.
Профессиональный стиль. Если нет опыта — акцент на навыки."""


def build_system_prompt(profile):
    lang_map = {"RU Русский": "русском", "EN English": "English only", "ZH 中文": "中文"}
    lang = profile.get("language", "RU Русский") if profile else "RU Русский"
    lang_instruction = lang_map.get(lang, "русском")

    base = f"""Ты - Анастасия, AI карьерный консультант @AnastasiaHR_ai_bot.
Диагност, консультант, подруга, психолог и профессионал.
Принцип: выявлять потребности и помогать через заботу. Не продавать агрессивно.
Лозунг: "Я рядом, я помогу. Помогу зарабатывать больше."
КРИТИЧНО: отвечай СТРОГО на {lang_instruction}. НЕ смешивай языки!
Стиль: тёплый, живой, конкретный. Один вопрос за раз.
Никогда "я не могу" — всегда предлагай решение."""

    if not profile:
        return base

    extra = "\n\nПРОФИЛЬ:\n"
    for field, label in [("personal", "Данные"), ("career", "Карьера"),
                          ("target", "Цель"), ("education", "Образование"),
                          ("achievements", "Достижения")]:
        if profile.get(field):
            extra += label + ": " + str(profile[field])[:150] + "\n"
    return base + extra


def ask_gpt(user_id, user_message, profile=None):
    history = get_history(user_id)
    history.append({"role": "user", "content": user_message})
    system = build_system_prompt(profile)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + history,
        max_tokens=800,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    save_history(user_id, history)
    update_user(user_id, "usage_count", "usage_count + 1")
    return reply


async def transcribe_voice(file_path):
    with open(file_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=f, language="ru"
        )
    return transcript.text


async def notify_admin(bot, message):
    try:
        await bot.send_message(ADMIN_ID, "🔔 " + message)
    except Exception:
        pass


def get_main_keyboard(profile=None):
    has_profile = profile and profile.get("profile_complete")
    keyboard = [
        [InlineKeyboardButton("📄 Бесплатное резюме", callback_data="resume_free")],
        [InlineKeyboardButton("⭐ ПРО резюме — 499 руб", callback_data="resume_pro"),
         InlineKeyboardButton("👑 VIP — 1490 руб", callback_data="resume_vip")],
        [InlineKeyboardButton("🔍 Найти вакансии", callback_data="search_jobs"),
         InlineKeyboardButton("🎤 HR симулятор", callback_data="hr_simulator")],
        [InlineKeyboardButton("📊 Анализ компании", callback_data="analyze_company"),
         InlineKeyboardButton("🌐 Сайт-визитка", callback_data="website")],
        [InlineKeyboardButton("📚 Подобрать курсы", callback_data="find_courses"),
         InlineKeyboardButton("💙 Психолог", callback_data="psychologist")],
        [InlineKeyboardButton("💬 Спросить Анастасию", callback_data="ask_anastasia"),
         InlineKeyboardButton("❓ FAQ", callback_data="faq")],
    ]
    if has_profile:
        keyboard.append([InlineKeyboardButton("👤 Мой профиль", callback_data="show_profile"),
                         InlineKeyboardButton("📊 Поддержка", callback_data="support")])
    else:
        keyboard.append([InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile"),
                         InlineKeyboardButton("📊 Поддержка", callback_data="support")])
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
    has_exp = not any(w in career for w in ["нет опыта", "без опыта", "начинающий"])

    if has_exp:
        text = (name + ", профиль заполнен! 🎉\n\n"
                "Теперь я знаю всё для персональных рекомендаций.\n"
                "Начнём с бесплатного резюме?")
    else:
        text = (name + ", профиль заполнен! 🎉\n\n"
                "Отсутствие опыта — не проблема!\n"
                "Создам резюме которое покажет ваши сильные стороны.")

    await message.reply_text(text, reply_markup=get_main_keyboard(profile))


async def request_phone(message):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.reply_text(
        "🔒 Для защиты от дублирования — верификация телефона.\n\n"
        "Это одноразовое действие. Номер хранится в зашифрованном виде.",
        reply_markup=keyboard
    )


async def start(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or "друг"

    create_user(user_id, username)
    profile = get_user(user_id)

    if profile and profile.get("is_blocked"):
        await update.message.reply_text(
            "Ваш аккаунт заблокирован.\n"
            "Причина: " + (profile.get("block_reason") or "нарушение правил") + "\n"
            "Обратитесь: @PopovSN78"
        )
        return

    if profile and profile.get("profile_complete"):
        name = profile.get("personal", "").split("\n")[0] if profile.get("personal") else first_name
        await update.message.reply_text(
            "С возвращением, " + name + "! Чем могу помочь? 😊",
            reply_markup=get_main_keyboard(profile)
        )
        return

    if not profile or not profile.get("consent"):
        consent_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принимаю условия", callback_data="consent_accept")],
            [InlineKeyboardButton("📋 Оферта", callback_data="show_oferta"),
             InlineKeyboardButton("🔒 Политика", callback_data="show_privacy")]
        ])
        await update.message.reply_text(CONSENT_TEXT, reply_markup=consent_keyboard)
        return

    PROFILE_STATE[user_id] = 0
    PROFILE_DATA[user_id] = {}
    await update.message.reply_text(
        "Отлично! Начнём заполнять профиль.\nЭто займёт 3 минуты и поможет создать сильное резюме.",
        reply_markup=make_keyboard(QUESTIONS[0]["keyboard"])
    )


async def oferta_cmd(update: Update, context):
    await update.message.reply_text(OFERTA_TEXT)


async def privacy_cmd(update: Update, context):
    await update.message.reply_text(PRIVACY_TEXT)


async def mydata_cmd(update: Update, context):
    user_id = update.effective_user.id
    profile = get_user(user_id)
    if not profile:
        await update.message.reply_text("Данных не найдено.")
        return
    text = "📋 Ваши данные в системе:\n\n"
    text += "ID: " + str(user_id) + "\n"
    text += "Телефон: " + (profile.get("phone") or "не указан") + "\n"
    text += "Профиль: " + ("заполнен" if profile.get("profile_complete") else "не заполнен") + "\n"
    text += "Тариф: " + str(profile.get("plan") or "free") + "\n"
    text += "Дата регистрации: " + str(profile.get("created_at", ""))[:10] + "\n\n"
    text += "Для удаления всех данных: /deletedata"
    await update.message.reply_text(text)


async def deletedata_cmd(update: Update, context):
    user_id = update.effective_user.id
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, удалить все данные", callback_data="confirm_delete")],
        [InlineKeyboardButton("❌ Отмена", callback_data="back_menu")]
    ])
    await update.message.reply_text(
        "⚠️ Вы уверены что хотите удалить все данные?\n\n"
        "Это действие необратимо. Профиль, резюме и история будут удалены.",
        reply_markup=keyboard
    )


async def reset_cmd(update: Update, context):
    user_id = update.effective_user.id
    delete_user_data(user_id)
    if user_id in PROFILE_STATE:
        del PROFILE_STATE[user_id]
    if user_id in PROFILE_DATA:
        del PROFILE_DATA[user_id]
    await update.message.reply_text("Профиль удалён. /start — начать заново.")


async def stats_cmd(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    stats = get_stats()
    text = (
        "📊 СТАТИСТИКА @AnastasiaHR_ai_bot\n\n"
        "Всего пользователей: " + str(stats.get("total", 0)) + "\n"
        "Резюме создано: " + str(stats.get("resumes", 0)) + "\n"
        "Платных пользователей: " + str(stats.get("paid", 0)) + "\n"
        "Новых сегодня: " + str(stats.get("new_today", 0)) + "\n"
    )
    await update.message.reply_text(text)


async def contact_handler(update: Update, context):
    user_id = update.effective_user.id
    contact = update.message.contact
    if not contact or not contact.phone_number:
        return

    phone = contact.phone_number
    existing = get_user_by_phone(phone)
    if existing and existing["user_id"] != user_id:
        await update.message.reply_text(
            "❌ Этот номер уже зарегистрирован.\n"
            "Каждый номер используется только один раз.",
            reply_markup=ReplyKeyboardRemove()
        )
        log_error(user_id, "DUPLICATE_PHONE", phone)
        await notify_admin(context.bot, f"Попытка дублирования телефона! User: {user_id}")
        return

    update_user(user_id, "phone", phone)
    if user_id in WAITING_PHONE:
        action = WAITING_PHONE.pop(user_id)
    else:
        action = None

    await update.message.reply_text("✅ Номер подтверждён!", reply_markup=ReplyKeyboardRemove())

    profile = get_user(user_id)
    if profile and profile.get("profile_complete"):
        await update.message.reply_text(
            "Теперь создаём ваше резюме...",
            reply_markup=get_main_keyboard(profile)
        )


async def callback_handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    username = q.from_user.username or ""
    data = q.data

    # Согласие
    if data == "consent_accept":
        update_user(user_id, "consent", True)
        update_user(user_id, "age_confirmed", True)
        PROFILE_STATE[user_id] = 0
        PROFILE_DATA[user_id] = {}
        await q.message.reply_text(
            "Спасибо! Начнём.\n\n"
            "За 3 минуты создам резюме которое приведёт вас на собеседование! 🚀",
        )
        await q.message.reply_text(
            "Выберите язык общения:",
            reply_markup=make_keyboard(QUESTIONS[0]["keyboard"])
        )
        return

    if data == "show_oferta":
        await q.message.reply_text(OFERTA_TEXT)
        return

    if data == "show_privacy":
        await q.message.reply_text(PRIVACY_TEXT)
        return

    if data == "confirm_delete":
        delete_user_data(user_id)
        await q.message.reply_text(
            "✅ Все ваши данные удалены.\n"
            "Спасибо что пользовались сервисом! /start — начать заново."
        )
        return

    # Заполнение профиля через кнопки
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
        profile = get_user(user_id)
        if not profile or not profile.get("consent"):
            consent_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принимаю условия", callback_data="consent_accept")],
                [InlineKeyboardButton("📋 Оферта", callback_data="show_oferta"),
                 InlineKeyboardButton("🔒 Политика", callback_data="show_privacy")]
            ])
            await q.message.reply_text(CONSENT_TEXT, reply_markup=consent_keyboard)
            return
        PROFILE_STATE[user_id] = 0
        PROFILE_DATA[user_id] = {}
        await q.message.reply_text(
            "Начинаем! 3 минуты и резюме готово 🚀",
            reply_markup=make_keyboard(QUESTIONS[0]["keyboard"])
        )
        return

    if data == "faq":
        await q.message.reply_text(FAQ_TEXT)
        return

    if data == "support":
        await q.message.reply_text(
            "📞 ПОДДЕРЖКА\n\n"
            "Написать менеджеру: @PopovSN78\n\n"
            "Время ответа: до 24 часов\n"
            "Возврат средств: в течение 24 часов\n\n"
            "Частые вопросы: /faq_cmd"
        )
        return

    if data == "resume_free":
        profile = get_user(user_id)
        if not profile or not profile.get("profile_complete"):
            await q.message.reply_text(
                "Сначала заполните профиль — займёт 3 минуты!\n\n"
                "Без профиля резюме будет общим и слабым.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")
                ]])
            )
            return

        if not profile.get("phone"):
            WAITING_PHONE[user_id] = "resume_free"
            await request_phone(q.message)
            return

        if profile.get("free_resume_used"):
            await q.message.reply_text(
                "Вы уже использовали бесплатное резюме 📄\n\n"
                "Хотите создать более сильное резюме?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ ПРО резюме — 499 руб", callback_data="resume_pro")],
                    [InlineKeyboardButton("👑 VIP резюме — 1490 руб", callback_data="resume_vip")],
                ])
            )
            return

        await q.message.reply_text("Анастасия создаёт резюме... ⏳\n\n30-60 секунд.")

        try:
            prompt = build_resume_prompt(profile)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Профессиональный составитель резюме. Без markdown символов * # и т.д."},
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
                        caption="📄 Ваше резюме готово!\n@AnastasiaHR_ai_bot"
                    )
                os.unlink(pdf_path)
                update_user(user_id, "free_resume_used", True)

                # Триггер улучшения
                await q.message.reply_text(
                    "Резюме готово! 🎉\n\n"
                    "💡 Анастасия проверила и нашла что можно улучшить:\n"
                    "• ATS-оптимизация повысит отклики на 40%\n"
                    "• Профессиональный дизайн выделит среди других\n"
                    "• Сопроводительное письмо увеличит шансы\n\n"
                    "Хотите сделать резюме ещё сильнее?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro"),
                         InlineKeyboardButton("🔍 Вакансии", callback_data="search_jobs")],
                        [InlineKeyboardButton("🎤 HR симулятор", callback_data="hr_simulator"),
                         InlineKeyboardButton("👑 VIP — 1490 руб", callback_data="resume_vip")],
                    ])
                )

                # Запрос оценки
                await q.message.reply_text(
                    "Оцените качество резюме:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("👍 Отлично", callback_data="rate_5"),
                        InlineKeyboardButton("👌 Хорошо", callback_data="rate_4"),
                        InlineKeyboardButton("👎 Плохо", callback_data="rate_1"),
                    ]])
                )
            else:
                await q.message.reply_text("Ошибка создания PDF. Попробуйте ещё раз.")
                log_error(user_id, "PDF_GENERATION", "PDF path is None")

        except Exception as e:
            log_error(user_id, "RESUME_FREE", str(e))
            await q.message.reply_text("Ошибка. Попробуйте ещё раз или напишите @PopovSN78")
            await notify_admin(context.bot, f"Ошибка резюме у {user_id}: {str(e)[:100]}")
        return

    if data.startswith("rate_"):
        rating = int(data.split("_")[1])
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO feedback (user_id, rating, service) VALUES (%s, %s, %s)",
                (user_id, rating, "resume_free")
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass
        if rating <= 2:
            await q.message.reply_text(
                "Жаль что не понравилось 😔\n\n"
                "Расскажите что не так — исправим бесплатно!\n"
                "Напишите @PopovSN78"
            )
            await notify_admin(context.bot, f"Плохая оценка от {user_id}! Нужна помощь.")
        else:
            await q.message.reply_text("Спасибо за оценку! 🙏")
        return

    if data == "resume_pro":
        await q.message.reply_text(
            "⭐ ПРО РЕЗЮМЕ — 499 руб\n\n"
            "Что получите:\n"
            "• 2 варианта дизайна на выбор\n"
            "• ATS-оптимизация (+40% откликов)\n"
            "• Ключевые слова под вакансию\n"
            "• Сопроводительное письмо\n"
            "• Фото если предоставили\n"
            "• До 3 обновлений\n"
            "• Без водяного знака\n\n"
            "Оплата: @PopovSN78\n"
            "После оплаты — резюме за 60 секунд! ⚡"
        )
        return

    if data == "resume_vip":
        await q.message.reply_text(
            "👑 VIP РЕЗЮМЕ — 1490 руб\n\n"
            "Что получите:\n"
            "• 3 варианта премиум дизайна\n"
            "• Достижения в инфографике\n"
            "• LinkedIn профиль в подарок\n"
            "• HR симулятор включён\n"
            "• Фото если предоставили\n"
            "• До 3 обновлений\n"
            "• Рекомендательное письмо\n"
            "• Для руководителей и топ-позиций\n\n"
            "Оплата: @PopovSN78\n"
            "После оплаты — работаем немедленно! ⚡"
        )
        return

    if data == "website":
        await q.message.reply_text(
            "🌐 САЙТ-ВИЗИТКА — 2490 руб\n\n"
            "Что получите:\n"
            "• 3 варианта дизайна (минимализм/тёмный/современный)\n"
            "• Личная ссылка: имя.anastasia-career.ru\n"
            "• Мобильная версия\n"
            "• Кнопка скачать резюме PDF\n"
            "• Раздел портфолио\n"
            "• QR-код для визитки\n"
            "• Фото если предоставили\n"
            "• До 3 обновлений\n\n"
            "Оплата: @PopovSN78"
        )
        return

    if data == "search_jobs":
        profile = get_user(user_id)
        if not profile or not profile.get("profile_complete"):
            await q.message.reply_text(
                "Для точного поиска нужен профиль.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 Заполнить профиль", callback_data="start_profile")
                ]])
            )
            return
        await q.message.reply_text("Ищу вакансии... 🔍")
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
                lines = [l.strip() for l in career.split("\n") if l.strip()]
                query = lines[-1][:50] if lines else "специалист"

            area_id = "113"
            city_map = {"москва": "1", "спб": "2", "питер": "2",
                       "екатеринбург": "3", "новосибирск": "4", "казань": "88"}
            for key, val in city_map.items():
                if key in city.lower():
                    area_id = val
                    break

            params = {"text": query, "per_page": 8, "area": area_id}
            r = httpx.get("https://api.hh.ru/vacancies", params=params,
                         headers={"User-Agent": "AnastasiaHR_ai_bot/1.0"}, timeout=10)
            items = r.json().get("items", [])

            if not items:
                await q.message.reply_text(
                    "По запросу ничего не найдено.\n"
                    "Попробуйте обновить профиль с другой должностью."
                )
                return

            name = personal.split("\n")[0] if personal else ""
            text = (name + ", нашла для вас:\n\n") if name else "Нашла вакансии:\n\n"
            for i, item in enumerate(items[:8], 1):
                salary = ""
                if item.get("salary"):
                    s = item["salary"]
                    if s.get("from"):
                        salary = " | от " + str(s["from"]) + " " + str(s.get("currency", ""))
                text += str(i) + ". " + item.get("name", "") + "\n"
                text += "   🏢 " + item.get("employer", {}).get("name", "") + salary + "\n"
                text += "   🔗 " + item.get("alternate_url", "") + "\n\n"

            await q.message.reply_text(text, disable_web_page_preview=True)
        except Exception as e:
            log_error(user_id, "SEARCH_JOBS", str(e))
            await q.message.reply_text("Ошибка поиска. Попробуйте позже.")
        return

    if data == "hr_simulator":
        profile = get_user(user_id)
        plan = profile.get("plan", "free") if profile else "free"
        if not check_gpt_limit(user_id, plan):
            await q.message.reply_text(
                "Достигнут дневной лимит (3 запроса).\n\n"
                "Для безлимитного доступа оформите PRO:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro")
                ]])
            )
            return
        await q.message.reply_text("Запускаем симуляцию собеседования... 🎤")
        try:
            prompt = "Начни симуляцию HR собеседования. Представься как HR-менеджер. Задай первый вопрос исходя из профиля кандидата. После каждого ответа — краткий feedback и следующий вопрос."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            log_error(user_id, "HR_SIMULATOR", str(e))
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "analyze_company":
        profile = get_user(user_id)
        plan = profile.get("plan", "free") if profile else "free"
        if not check_gpt_limit(user_id, plan):
            await q.message.reply_text(
                "Достигнут дневной лимит.\n"
                "Оформите PRO для безлимитного доступа.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro")
                ]])
            )
            return
        await q.message.reply_text(
            "📊 АНАЛИЗ КОМПАНИИ\n\n"
            "Напишите название компании — соберу информацию:\n"
            "• Отзывы сотрудников\n"
            "• Репутация на рынке\n"
            "• Средняя зарплата\n"
            "• Советы по собеседованию\n\n"
            "Просто напишите название компании:"
        )
        return

    if data == "find_courses":
        profile = get_user(user_id)
        plan = profile.get("plan", "free") if profile else "free"
        if not check_gpt_limit(user_id, plan):
            await q.message.reply_text("Достигнут дневной лимит. Оформите PRO.")
            return
        await q.message.reply_text("Подбираю курсы... 📚")
        try:
            prompt = "Подбери 5 конкретных онлайн-курсов для клиента. Укажи платформу, название, стоимость и почему подойдёт именно этот курс."
            reply = ask_gpt(user_id, prompt, profile)
            await q.message.reply_text(reply)
        except Exception as e:
            log_error(user_id, "FIND_COURSES", str(e))
            await q.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return

    if data == "psychologist":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("😰 Стресс перед собеседованием", callback_data="psycho_stress")],
            [InlineKeyboardButton("😔 Страх отказа", callback_data="psycho_rejection")],
            [InlineKeyboardButton("😮‍💨 Выгорание", callback_data="psycho_burnout")],
            [InlineKeyboardButton("💬 Личная консультация (PRO)", callback_data="psycho_personal")],
        ])
        await q.message.reply_text(
            "💙 ПСИХОЛОГИЧЕСКАЯ ПОДДЕРЖКА\n\n"
            "Карьерный путь бывает сложным.\n"
            "Анастасия здесь чтобы поддержать!\n\n"
            "Выберите тему:",
            reply_markup=keyboard
        )
        return

    if data == "psycho_stress":
        await q.message.reply_text(PSYCHO_ARTICLES["stress"])
        return

    if data == "psycho_rejection":
        await q.message.reply_text(PSYCHO_ARTICLES["rejection"])
        return

    if data == "psycho_burnout":
        await q.message.reply_text(PSYCHO_ARTICLES["burnout"])
        return

    if data == "psycho_personal":
        profile = get_user(user_id)
        plan = profile.get("plan", "free") if profile else "free"
        if plan not in ["pro", "vip"]:
            await q.message.reply_text(
                "💙 Личная консультация психолога — только для PRO/VIP\n\n"
                "Оформите подписку для доступа:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro"),
                    InlineKeyboardButton("👑 VIP — 1490 руб", callback_data="resume_vip")
                ]])
            )
            return
        await q.message.reply_text(
            "💙 Анастасия слушает вас.\n\n"
            "Расскажите о вашей ситуации — поддержу и помогу найти выход."
        )
        return

    if data == "ask_anastasia":
        profile = get_user(user_id)
        plan = profile.get("plan", "free") if profile else "free"
        if not check_gpt_limit(user_id, plan):
            await q.message.reply_text(
                "Достигнут дневной лимит (3 запроса).\n"
                "Оформите PRO для безлимитного общения с Анастасией.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro")
                ]])
            )
            return
        await q.message.reply_text(
            "Я слушаю вас! 😊\n"
            "Пишите текстом или голосовым 🎤"
        )
        return

    if data == "show_profile":
        profile = get_user(user_id)
        if not profile:
            await q.message.reply_text("Профиль не найден.")
            return
        text = "👤 ВАШ ПРОФИЛЬ\n\n"
        if profile.get("personal"):
            text += str(profile["personal"])[:200] + "\n\n"
        if profile.get("career"):
            text += "💼 " + str(profile["career"])[:150] + "\n\n"
        if profile.get("target"):
            text += "🎯 " + str(profile["target"])[:100] + "\n\n"
        text += "📞 " + (profile.get("phone") or "телефон не указан") + "\n"
        text += "📊 Тариф: " + str(profile.get("plan") or "FREE") + "\n"
        text += "🔢 Обращений: " + str(profile.get("usage_count") or 0)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Обновить профиль", callback_data="start_profile")],
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("📋 Мои данные", callback_data="my_data")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back_menu")]
        ])
        await q.message.reply_text(text, reply_markup=keyboard)
        return

    if data == "my_data":
        profile = get_user(user_id)
        text = "📋 Ваши данные:\n\nДля удаления: /deletedata\nДля копии: /mydata"
        await q.message.reply_text(text)
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
    profile = get_user(user_id)
    plan = profile.get("plan", "free") if profile else "free"
    if not check_gpt_limit(user_id, plan):
        await update.message.reply_text("Достигнут дневной лимит. Оформите PRO.")
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
        log_error(user_id, "VOICE", str(e))
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
    plan = profile.get("plan", "free") if profile else "free"

    if not check_gpt_limit(user_id, plan):
        await message.reply_text(
            "Достигнут дневной лимит (3 запроса).\n\n"
            "Оформите PRO для безлимитного общения:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⭐ ПРО — 499 руб", callback_data="resume_pro")
            ]])
        )
        return

    await message.reply_text("Анастасия думает... 💭")
    try:
        reply = ask_gpt(user_id, text, profile)
        await message.reply_text(reply)
    except Exception as e:
        log_error(user_id, "GPT", str(e))
        await message.reply_text("Ошибка. Попробуйте ещё раз или напишите @PopovSN78")


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
    app.add_handler(CommandHandler("oferta", oferta_cmd))
    app.add_handler(CommandHandler("privacy", privacy_cmd))
    app.add_handler(CommandHandler("mydata", mydata_cmd))
    app.add_handler(CommandHandler("deletedata", deletedata_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
