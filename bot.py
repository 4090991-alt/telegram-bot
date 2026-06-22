import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ NO TOKEN FOUND")
    raise SystemExit()

logging.basicConfig(level=logging.INFO)

print("BOT STARTED OK")

USER = {}

# =========================
# STORAGE
# =========================
USER_STATE = {}
USER_DATA = {}
USER_PROFILE = {}

# =========================
# MENU
# =========================
def get_connector(mode):
    return {
        "free": ["РЕЗЮМЕ", "Вакансии", "HR интервью"],
        "pro": ["VIP резюме", "Сайт-визитка", "Анализ рынка"],
        "vip": ["VIP стратегия", "CEO интервью", "Закрытие позиции"]
    }.get(mode, [])

# =========================
# INTENT DETECTOR
# =========================
def detect_intent(text: str):
    text = text.lower()

    if "резюме" in text:
        return "resume_build"
    if "работ" in text:
        return "job_search"
    if "профес" in text:
        return "career_change"
    if "интервью" in text:
        return "interview_prep"

    return "unknown"

# =========================
# 🧠 DECISION ENGINE (ЭТАП 2)
# =========================
def decision_engine(profile):
    try:
        age = int(profile.get("age"))
    except:
        age = None

    goal = profile.get("goal", "")
    exp = profile.get("experience", "")

    if age and age < 18:
        return "education_path"

    if "смена" in goal:
        return "career_change_path"

    if "деньги" in goal:
        return "growth_path"

    if exp and ("10" in exp or "20" in exp):
        return "senior_path"

    return "resume_path"

# =========================
# 🧭 ROUTING ENGINE (ЭТАП 3) ⭐
# =========================
def route_engine(path):
    routes = {
        "education_path": "prof_orientation_module",
        "career_change_path": "career_change_module",
        "growth_path": "vacancy_module",
        "senior_path": "vip_strategy_module",
        "resume_path": "resume_module"
    }

    return routes.get(path, "resume_module")

# =========================
# START
# =========================
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("FREE", callback_data="free")],
        [InlineKeyboardButton("PRO", callback_data="pro")],
        [InlineKeyboardButton("VIP", callback_data="vip")],
        [InlineKeyboardButton("📄 РЕЗЮМЕ", callback_data="resume")]
    ]

    await update.message.reply_text(
        "🚀 CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK
# =========================
async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id

    if q.data in ["free", "pro", "vip"]:
        USER[user_id] = q.data
        await q.message.reply_text(f"✅ {q.data.upper()} MODE ACTIVE")

        for step in get_connector(q.data):
            await q.message.reply_text("➡️ " + step)

    elif q.data == "resume":
        USER_STATE[user_id] = "resume_name"
        USER_DATA[user_id] = {}
        await q.message.reply_text("📄 Введите ваше ФИО:")

# =========================
# PROFILE + RESUME FLOW
# =========================
async def resume_flow(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text

    # =========================
    # INTENT
    # =========================
    intent = detect_intent(text)

    # =========================
    # PROFILE START
    # =========================
    if intent in ["job_search", "career_change"]:
        USER_PROFILE[user_id] = {
            "intent": intent,
            "step": "age"
        }
        await update.message.reply_text("🧠 Сколько вам лет?")
        return

    # =========================
    # PROFILE FLOW
    # =========================
    if user_id in USER_PROFILE:
        profile = USER_PROFILE[user_id]

        if profile["step"] == "age":
            profile["age"] = text
            profile["step"] = "experience"
            await update.message.reply_text("💼 Какой у вас опыт работы?")
            return

        if profile["step"] == "experience":
            profile["experience"] = text
            profile["step"] = "field"
            await update.message.reply_text("🏢 В какой сфере вы работали?")
            return

        if profile["step"] == "field":
            profile["field"] = text
            profile["step"] = "goal"
            await update.message.reply_text("🎯 Что вам важнее: деньги / рост / смена профессии?")
            return

        if profile["step"] == "goal":
            profile["goal"] = text
            profile["step"] = "done"

            # =========================
            # DECISION + ROUTING (ЭТАП 2 + 3)
            # =========================
            path = decision_engine(profile)
            module = route_engine(path)

            profile["path"] = path
            profile["module"] = module

            USER_PROFILE[user_id] = profile

            await update.message.reply_text(
                f"✅ Профиль готов\n🧠 Path: {path}\n🚀 Module: {module}"
            )

            print("PROFILE:", USER_PROFILE[user_id])
            return

    # =========================
    # RESUME FLOW (OLD)
    # =========================
    if user_id not in USER_STATE:
        return

    state = USER_STATE[user_id]

    if state == "resume_name":
        USER_DATA[user_id]["name"] = text
        USER_STATE[user_id] = "resume_exp"
        await update.message.reply_text("💼 Опыт работы (кратко):")

    elif state == "resume_exp":
        USER_DATA[user_id]["exp"] = text
        USER_STATE[user_id] = "resume_skills"
        await update.message.reply_text("🧠 Навыки:")

    elif state == "resume_skills":
        USER_DATA[user_id]["skills"] = text

        data = USER_DATA[user_id]

        resume = f"""
📄 РЕЗЮМЕ

👤 ФИО: {data['name']}

💼 Опыт:
{data['exp']}

🧠 Навыки:
{data['skills']}

━━━━━━━━━━━━━━
AI CAREER BOT
"""

        await update.message.reply_text(resume)

        del USER_STATE[user_id]
        del USER_DATA[user_id]

# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))

    print("RUNNING...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )

if __name__ == "__main__":
    main()
