import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    print("NO TOKEN FOUND")
    raise SystemExit()

logging.basicConfig(level=logging.INFO)
print("BOT STARTED OK")

USER = {}
USER_STATE = {}
USER_DATA = {}
USER_PROFILE = {}


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


def get_connector(mode):
    data = {
        "free": ["RESUME", "Vacancies", "HR interview"],
        "pro": ["VIP resume", "Website", "Market analysis"],
        "vip": ["VIP strategy", "CEO interview", "Position closing"],
    }
    return data.get(mode, [])


def detect_intent(text):
    text = text.lower()
    if "resume" in text or "rezume" in text:
        return "resume_build"
    if "work" in text or "job" in text or "rabota" in text:
        return "job_search"
    if "career" in text or "karera" in text:
        return "career_change"
    if "interview" in text:
        return "interview_prep"
    return "unknown"


def decision_engine(profile):
    try:
        age = int(profile.get("age", 0))
    except Exception:
        age = 0
    goal = profile.get("goal", "")
    exp = profile.get("experience", "")
    if age and age < 18:
        return "education_path"
    if "change" in goal or "smena" in goal:
        return "career_change_path"
    if "money" in goal or "dengi" in goal:
        return "growth_path"
    if "10" in exp or "20" in exp:
        return "senior_path"
    return "resume_path"


def route_engine(path):
    routes = {
        "education_path": "prof_orientation_module",
        "career_change_path": "career_change_module",
        "growth_path": "vacancy_module",
        "senior_path": "vip_strategy_module",
        "resume_path": "resume_module",
    }
    return routes.get(path, "resume_module")


async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("FREE", callback_data="free")],
        [InlineKeyboardButton("PRO", callback_data="pro")],
        [InlineKeyboardButton("VIP", callback_data="vip")],
        [InlineKeyboardButton("RESUME", callback_data="resume")],
    ]
    await update.message.reply_text(
        "CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if q.data in ["free", "pro", "vip"]:
        USER[user_id] = q.data
        await q.message.reply_text(q.data.upper() + " MODE ACTIVE")
        for step in get_connector(q.data):
            await q.message.reply_text(step)
    elif q.data == "resume":
        USER_STATE[user_id] = "resume_name"
        USER_DATA[user_id] = {}
        await q.message.reply_text("Enter your full name:")


async def resume_flow(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text
    intent = detect_intent(text)

    if intent in ["job_search", "career_change"]:
        USER_PROFILE[user_id] = {"intent": intent, "step": "age"}
        await update.message.reply_text("How old are you?")
        return

    if user_id in USER_PROFILE:
        profile = USER_PROFILE[user_id]
        step = profile.get("step")
        if step == "age":
            profile["age"] = text
            profile["step"] = "experience"
            await update.message.reply_text("Work experience?")
            return
        if step == "experience":
            profile["experience"] = text
            profile["step"] = "field"
            await update.message.reply_text("What field?")
            return
        if step == "field":
            profile["field"] = text
            profile["step"] = "goal"
            await update.message.reply_text("Goal: money / growth / career change?")
            return
        if step == "goal":
            profile["goal"] = text
            profile["step"] = "done"
            path = decision_engine(profile)
            module = route_engine(path)
            profile["path"] = path
            profile["module"] = module
            USER_PROFILE[user_id] = profile
            await update.message.reply_text(
                "Profile ready\nPath: " + path + "\nModule: " + module
            )
            return

    if user_id not in USER_STATE:
        return

    state = USER_STATE[user_id]
    if state == "resume_name":
        USER_DATA[user_id]["name"] = text
        USER_STATE[user_id] = "resume_exp"
        await update.message.reply_text("Work experience:")
    elif state == "resume_exp":
        USER_DATA[user_id]["exp"] = text
        USER_STATE[user_id] = "resume_skills"
        await update.message.reply_text("Skills:")
    elif state == "resume_skills":
        USER_DATA[user_id]["skills"] = text
        data = USER_DATA[user_id]
        resume = (
            "RESUME\n\n"
            "Name: " + data["name"] + "\n\n"
            "Experience:\n" + data["exp"] + "\n\n"
            "Skills:\n" + data["skills"] + "\n\n"
            "AI CAREER BOT"
        )
        await update.message.reply_text(resume)
        del USER_STATE[user_id]
        del USER_DATA[user_id]


def main():
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    print("HEALTH SERVER RUNNING ON PORT " + str(PORT))

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, resume_flow))
    print("RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
