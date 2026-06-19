import os
from datetime import datetime
from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes
)
from openai import OpenAI

# =========================
# 🔑 KEYS
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

if not TELEGRAM_TOKEN:
    raise Exception("TELEGRAM_TOKEN not set")

if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set")

if not PROVIDER_TOKEN:
    raise Exception("PROVIDER_TOKEN not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# 👑 OWNER
# =========================

OWNER_ID = 0  # твой ID

# =========================
# 🧠 SYSTEM PROMPT (SAAS VERSION)
# =========================

SYSTEM_PROMPT = """
Ты — АНАСТАСИЯ, карьерный HR-консультант.

Ты работаешь как платный SaaS сервис.

Роли:
- помогать с резюме
- анализировать компании
- вакансии
- собеседования

Правила:
- женский род
- один ответ = один результат
- без фантазий
"""

# =========================
# 🧠 CRM CORE (SAAS STRUCTURE)
# =========================

users_db = {}
revenue = 0.0

FREE_LIMIT = 5

# user_state:
# free | pro | vip
user_state = {}

user_usage = {}

# =========================
# 📊 TRACK USER
# =========================

def track_user(user_id, username):
    if user_id not in users_db:
        users_db[user_id] = {
            "username": username,
            "created_at": datetime.now(),
            "messages": 0,
            "payments": 0
        }
        user_state[user_id] = "free"

# =========================
# 🛡 ACCESS LOGIC (SAAS RULES)
# =========================

def is_allowed(user_id):
    state = user_state.get(user_id, "free")

    if state in ["pro", "vip"]:
        return True

    return user_usage.get(user_id, 0) < FREE_LIMIT

def add_usage(user_id):
    state = user_state.get(user_id, "free")

    if state == "free":
        user_usage[user_id] = user_usage.get(user_id, 0) + 1

    if user_id in users_db:
        users_db[user_id]["messages"] += 1

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user.id, user.username)

    await update.message.reply_text(
        "Я АНАСТАСИЯ — карьерный HR SaaS ассистент.\n"
        "Напишите /services"
    )

# =========================
# 💼 SERVICES (SALES FUNNEL)
# =========================

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 Резюме PRO — 2490₽", callback_data="resume")],
        [InlineKeyboardButton("🏢 Анализ PRO — 1490₽", callback_data="company")],
        [InlineKeyboardButton("🎤 Собеседование PRO — 990₽", callback_data="interview")]
    ]

    await update.message.reply_text(
        "💼 SaaS УСЛУГИ АНАСТАСИИ\nВыберите продукт:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# 💳 PAYMENT SYSTEM
# =========================

async def send_invoice(update, title, price, plan):
    prices = [LabeledPrice(label=title, amount=int(price * 100))]

    await update.message.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=f"SaaS доступ: {plan}",
        payload=plan,
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=prices
    )

# =========================
# 🔘 BUTTON HANDLER
# =========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "resume":
        await send_invoice(query, "Резюме PRO", 2490, "pro")

    elif query.data == "company":
        await send_invoice(query, "Анализ PRO", 1490, "pro")

    elif query.data == "interview":
        await send_invoice(query, "Собеседование PRO", 990, "pro")

# =========================
# 💰 PAYMENT CONFIRM (UPGRADE SYSTEM)
# =========================

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global revenue

    user = update.effective_user

    user_state[user.id] = "pro"

    if user.id in users_db:
        users_db[user.id]["payments"] += 1

    revenue += update.message.successful_payment.total_amount / 100

    await update.message.reply_text(
        "✅ PRO доступ активирован!\nТеперь лимитов нет."
    )

# =========================
# 👑 ADMIN (FULL SAAS CONTROL)
# =========================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    free = sum(1 for u in user_state.values() if u == "free")
    pro = sum(1 for u in user_state.values() if u == "pro")

    await update.message.reply_text(
        f"📊 SAAS DASHBOARD\n\n"
        f"Free users: {free}\n"
        f"Pro users: {pro}\n"
        f"Revenue: {revenue:.2f} ₽"
    )

# =========================
# 💬 CHAT ENGINE
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    track_user(user.id, user.username)

    if not is_allowed(user.id):
        await update.message.reply_text(
            "❌ Лимит бесплатных сообщений исчерпан.\nОформите PRO доступ через /services"
        )
        return

    add_usage(user.id)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )

        await update.message.reply_text(
            response.choices[0].message.content[:3500]
        )

    except Exception:
        await update.message.reply_text("Ошибка сервера.")

# =========================
# ⚙️ APP
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("services", services))
app.add_handler(CommandHandler("admin", admin))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(PreCheckoutQueryHandler(precheckout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
