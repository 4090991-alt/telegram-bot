from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import os

# =========================
# 🔐 ENV (Render SAFE MODE)
# =========================
client = OpenAI(api_key=os.getenv("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"))
TOKEN = os.getenv("8980383832:AAGimFRvuk-cvDl21mQPasyM_48Bhr71B-E")

# =========================
# 📋 МЕНЮ
# =========================
menu = ReplyKeyboardMarkup(
    [
        ["📄 Резюме", "💼 Вакансии"],
        ["🏢 Компании", "🎤 Собеседование"]
    ],
    resize_keyboard=True
)

# =========================
# 🧠 ПАМЯТЬ ПОЛЬЗОВАТЕЛЯ
# =========================
user_data = {}

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я Анастасия 🤖\nВыбери действие:",
        reply_markup=menu
    )

# =========================
# MAIN HANDLER
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.chat_id

    if user_id not in user_data:
        user_data[user_id] = {"step": None, "data": {}}

    state = user_data[user_id]

    # =========================
    # 📄 RESUME MODULE
    # =========================
    if text == "📄 Резюме":
        state["step"] = "level"
        await update.message.reply_text(
            "Выберите уровень резюме:\n"
            "1️⃣ Basic\n"
            "2️⃣ ATS\n"
            "3️⃣ 💎 VIP"
        )
        return

    if state["step"] == "level":
        state["data"]["level"] = text
        state["step"] = "country"
        await update.message.reply_text("В какой стране вы ищете работу?")
        return

    if state["step"] == "country":
        state["data"]["country"] = text
        state["step"] = "name"
        await update.message.reply_text("Введите ФИО")
        return

    if state["step"] == "name":
        state["data"]["name"] = text
        state["step"] = "exp"
        await update.message.reply_text("Опыт работы (кратко)")
        return

    if state["step"] == "exp":
        state["data"]["exp"] = text
        state["step"] = "skills"
        await update.message.reply_text("Навыки и компетенции")
        return

    if state["step"] == "skills":
        state["data"]["skills"] = text

        level = state["data"].get("level", "1")

        if "3" in level or "VIP" in level:
            style = "СДЕЛАЙ VIP EXECUTIVE РЕЗЮМЕ (уровень топ-менеджмента)"
        elif "2" in level or "ATS" in level:
            style = "СДЕЛАЙ ATS-ОПТИМИЗИРОВАННОЕ РЕЗЮМЕ"
        else:
            style = "СДЕЛАЙ СТАНДАРТНОЕ РЕЗЮМЕ"

        prompt = f"""
{style}

ФИО: {state['data']['name']}
Страна: {state['data']['country']}
Опыт: {state['data']['exp']}
Навыки: {state['data']['skills']}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты эксперт по резюме мирового уровня."},
                {"role": "user", "content": prompt}
            ]
        )

        await update.message.reply_text(response.choices[0].message.content)

        user_data[user_id] = {"step": None, "data": {}}
        return

    # =========================
    # 🤖 GPT FALLBACK
    # =========================
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты карьерный ассистент Анастасия."},
            {"role": "user", "content": text}
        ]
    )

    await update.message.reply_text(response.choices[0].message.content)

# =========================
# 🚀 START BOT (RENDER READY)
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
