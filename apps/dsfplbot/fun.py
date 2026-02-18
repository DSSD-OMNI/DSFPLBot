import random
import json
import csv
import os
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.dsfplbot.database import add_score, get_scores

logger = logging.getLogger(__name__)

# ---------- DoubleQuiz ----------
async def generate_league_question():
    """Генерирует вопрос по истории лиги из CSV."""
    csv_path = "apps/dsfplbot/FPL League History.csv"
    try:
        if not os.path.exists(csv_path):
            return {"question": "Кто выиграл лигу в сезоне 2023/24?", "answer": "Peter Popov"}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            if not reader:
                return {"question": "Кто выиграл лигу в сезоне 2023/24?", "answer": "Peter Popov"}
            row = random.choice(reader)
            season = row["Season"]
            winner = row["Manager"]
            return {
                "question": f"Кто занял 1-е место в лиге в сезоне {season}?",
                "answer": winner
            }
    except Exception as e:
        logger.error(f"Error generating league question: {e}")
        return {"question": "Кто выиграл лигу в сезоне 2023/24?", "answer": "Peter Popov"}

async def dq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сегодняшние вопросы."""
    today = date.today().isoformat()
    league_q = await generate_league_question()
    try:
        with open("apps/dsfplbot/questions.json", "r", encoding="utf-8") as f:
            football_questions = json.load(f)
        football_q = random.choice(football_questions) if football_questions else {"question": "Заглушка", "answer": "Ответ"}
    except Exception as e:
        logger.error(f"Error loading questions.json: {e}")
        football_q = {"question": "Кто выиграл ЧМ-2018?", "answer": "Франция"}
    context.bot_data[f"quiz_{today}"] = {"q1": league_q, "q2": football_q}
    text = (
        f"🎯 *DoubleQuiz на {today}*\n\n"
        f"1️⃣ {league_q['question']}\n"
        f"2️⃣ {football_q['question']}\n\n"
        "Ответы отправляйте в формате:\n"
        "/answer 1 ваш_ответ\n"
        "/answer 2 ваш_ответ"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на вопрос."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Использование: /answer 1 <ответ>")
            return
        q_num = int(args[0])
        user_answer = " ".join(args[1:]).strip().lower()
        today = date.today().isoformat()
        if f"quiz_{today}" not in context.bot_data:
            await update.message.reply_text("На сегодня вопросы ещё не заданы. Введите /dq")
            return
        quiz = context.bot_data[f"quiz_{today}"]
        if q_num == 1:
            correct = quiz['q1']['answer'].lower()
        elif q_num == 2:
            correct = quiz['q2']['answer'].lower()
        else:
            await update.message.reply_text("Номер вопроса должен быть 1 или 2.")
            return
        if user_answer == correct:
            await add_score(update.effective_user.id, "dq", 1)
            await update.message.reply_text("✅ Правильно! +1 очко.")
        else:
            await update.message.reply_text(f"❌ Неправильно. Правильный ответ: {correct}")
    except Exception as e:
        logger.error(f"Error in answer: {e}")
        await update.message.reply_text("Ошибка обработки ответа.")

# ---------- Остальные игры (заглушки) ----------
async def gtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Guess The Diff временно недоступен.")

async def predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Чемпионат прогнозов в разработке.")

async def scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        scores = await get_scores("dq")
        if not scores:
            await update.message.reply_text("Таблица лидеров по DoubleQuiz пуста.")
            return
        text = "🏆 *Таблица лидеров DoubleQuiz*\n\n"
        for i, (user_id, score, attempts) in enumerate(scores[:10], 1):
            text += f"{i}. `{user_id}` – {score} очков (попыток: {attempts})\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in scoreboard: {e}")
        await update.message.reply_text("Ошибка получения таблицы.")

async def fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 DoubleQuiz", callback_data="fun_dq")],
        [InlineKeyboardButton("🔮 Guess The Diff", callback_data="fun_gtd")],
        [InlineKeyboardButton("📊 Чемпионат прогнозов", callback_data="fun_predict")],
        [InlineKeyboardButton("🏆 Таблицы", callback_data="fun_scoreboard")],
    ]
    await update.message.reply_text(
        "🎮 *Mutantos Game Arena*\n\nВыберите игру:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def fun_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "fun_dq":
        await dq(update, context)
    elif data == "fun_gtd":
        await gtd(update, context)
    elif data == "fun_predict":
        await predictions(update, context)
    elif data == "fun_scoreboard":
        await scoreboard(update, context)
    elif data.startswith("score_"):
        game = data.replace("score_", "")
        if game == "dq":
            await scoreboard(update, context)
        else:
            await query.edit_message_text(f"Таблица для игры {game} пока не готова.")

async def daily_quiz_job(context: ContextTypes.DEFAULT_TYPE):
    """Заглушка для ежедневной викторины."""
    logger.info("daily_quiz_job called (stub)")
