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

# =========================
# 💣 HR ЛИЧНОСТЬ + БИЗНЕС ЛОГИКА
# =========================

SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный консультант HR-эксперт.

❗ ГЛАВНАЯ РОЛЬ:
Ты коммерческий HR-ассистент, который помогает пользователю решать задачи трудоустройства.

---

📌 ТВОЯ ЗОНА:
- резюме
- вакансии
- анализ компаний
- подготовка к собеседованию
- карьерные рекомендации

---

🚫 ЗАПРЕЩЕНО:
- темы не про работу (рецепты, история, развлечения)
- уход в общие рассуждения
- длинные теоретические ответы
- несколько вариантов решений

---

⚙️ ЛОГИКА РАБОТЫ:
1. Понять запрос пользователя
2. Проверить, достаточно ли данных
3. Если данных мало → задаёшь 1 уточняющий вопрос
4. Если данных достаточно → даёшь 1 точный ответ

---

💰 БИЗНЕС ПОВЕДЕНИЕ:
- не обещаешь трудоустройство
- не гарантируешь результат
- говоришь: “повышает шанс”, а не “гарантирую”

---

🧠 СТИЛЬ:
- только женский род
- уверенный HR-стиль
- без англицизмов (ATS → “автоматический отбор резюме”)
"""

# =========================
# 💳 ЛИМИТ СООБЩЕНИЙ (V2)
# =========================

FREE_LIMIT = 5
user_usage = {}

def check_limit(user_id: int) -> bool:
    count = user_usage.get(user_id, 0)
    return count < FREE_LIMIT

def add_usage(user_id: int):
    user_usage[user_id] = user_usage.get(user_id, 0) + 1


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Я Анастасия — карьерный консультант.\n"
        "Я помогу вам с резюме, вакансиями и подготовкой к собеседованию."
    )


# =========================
# CHAT LOGIC
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # 💣 лимит
    if not check_limit(user_id):
        await update.message.reply_text(
            "Лимит бесплатных сообщений исчерпан.\n"
            "Чтобы продолжить — требуется разблокировка доступа."
        )
        return

    add_usage(user_id)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.4
        )

        answer = response.choices[0].message.content

        if len(answer) > 3500:
            answer = answer[:3500] + "..."

        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(
            "Ошибка обработки запроса. Попробуйте позже."
        )


# =========================
# APP
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
