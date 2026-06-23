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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    print("❌ NO TOKEN FOUND")
    raise SystemExit()

logging.basicConfig(level=logging.INFO)
print("BOT STARTED OK")

USER = {}
USER_STATE = {}
USER_DATA = {}
USER_PROFILE = {}

def get_connector(mode):
    return {
        "free": ["РЕЗЮМЕ", "Вакансии", "HR интервью"],
        "pro": ["VIP резюме", "Сайт-визитка", "Анализ рынка"],
        "vip": ["VIP стратегия", "CEO интервью", "Закрытие позиции"]
    }.get(mode, [])

def detect_intent(text: str):
    text = text.lower()
    if "резюме" in text: return "resume_build"
    if "работ" in text: return "job_search"
    if "профес" in text: return "career_change"
    if "интервью" in text: return "interview_prep"
    return "unknown"

def decision_engine(profile):
    try:
        age = int(profile.get("age"))
    except:
        age = None
    goal = profile.get("goal", "")
    exp = profile.get("experience", "")
    if age and age < 18: return "education_path"
    if "смена" in goal: return "career_change_path"
    if "деньги" in goal: return "growth_path"
    if exp and ("10" in exp or "20" in exp): return "senior_path"
    return
