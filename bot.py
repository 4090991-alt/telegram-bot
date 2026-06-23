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
        "vip": ["VIP strategy", "CEO interview", "Position closing"]
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
        "resume_path": "resume_module"
    }
    return routes.get(path, "resume_module")

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("FREE", callback_data="free")],
        [InlineKeyboardButton("PRO", callback_data="pro")],
        [InlineKeyboardButton("VIP", callback_data="vip")],
        [InlineKeyboardButton("RESUME", callback_data="resume")]
    ]
    await update.message.reply_text(
        "CAREER ENGINE ONLINE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handler(update: Update, context):
    q = update.callback_query
    await
