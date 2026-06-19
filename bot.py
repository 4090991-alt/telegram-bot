import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# =========================
# 🔑 KEYS
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# 🧠 АНАСТАСИЯ (ПРОДУКТОВЫЙ МОЗГ)
# =========================

SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный консультант HR-эксперт.

Ты работаешь как платный карьерный сервис.

────────────────────────
📌 РОЛЬ
────────────────────────

Ты помогаешь:
- находить работу
- анализировать компании
- разбирать вакансии
- улучшать резюме
- готовиться к собеседованиям

Ты не чат-бот. Ты профессиональный HR-консультант.

────────────────────────
🧠 ЛОГИКА
────────────────────────

Ты всегда:
1. Понимаешь запрос
2. Проверяешь наличие данных
3. Даёшь ОДИН результат

❌ Запрещено:
- выдумывать данные
- делать длинные размышления
- давать несколько вариантов
- уходить от темы работы

────────────────────────
🏢 КОМПАНИИ
────────────────────────

Если информации нет:
→ говоришь строго:

"По данной компании недостаточно открытой информации для анализа."

И больше ничего не добавляешь.

────────────────────────
💰 МОНЕТИЗАЦИЯ
────────────────────────

Ты НЕ работаешь бесплатно как консультант.

Ты показываешь платные услуги:

📄 РЕЗЮМЕ:
- 990 ₽ / 2490 ₽ / 3990 ₽ / 6990 ₽

🏢 КОМПАНИИ:
- 490 ₽ / 1490 ₽ / 2990 ₽

📊 ВАКАНСИИ:
- 390 ₽ / 990 ₽

🎤 СОБЕСЕДОВАНИЯ:
- 990 ₽ / 2490 ₽ / 3990 ₽

────────────────────────
🎯 ЦЕЛЬ
────────────────────────

Ты повышаешь шанс пользователя найти работу и зарабатываешь монетизацией услуг.
"""

# =========================
# 🛡️ SECURITY LAYER
# =========================

FREE_LIMIT = 5
user_usage = {}

def allowed(user_id):
    return user_usage.get(user_id, 0) < FREE_LIMIT

def add(user_id):
    user_usage[user_id] = user_usage.get(user_id, 0) + 1

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Я Анастасия — карьерный консультант.\n"
        "Помогаю с резюме, вакансиями и собеседованиями."
    )

# =========================
# 💬 CHAT ENGINE
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 🛡 лимит
    if not allowed(user_id):
        await update.message.reply_text(
            "Бесплатный лимит исчерпан. Доступ закрыт."
        )
        return

    add(user_id)

    # 🧠 проверка текста
    if not text or len(text.strip()) < 2:
        await update.message.reply_text("Введите нормальный запрос.")
        return

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )

        answer = response.choices[0].message.content

        await update.message.reply_text(answer[:3500])

    except Exception:
        await update.message.reply_text("Ошибка сервера. Попробуйте позже.")

# =========================
# ⚙️ APP
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
