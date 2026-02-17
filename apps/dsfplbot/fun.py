import random
import json
import asyncio
from datetime import datetime, date
from collections import Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.dsfplbot.database import add_score, get_scores
from apps.dsfplbot.fpl_api import get_bootstrap_static, get_event_live, get_current_event
import logging
import os

logger = logging.getLogger(__name__)

# ========== DoubleQuiz ==========

async def generate_league_question():
    """Генерирует вопрос по истории лиги из CSV."""
    try:
        import csv
        csv_path = "apps/dsfplbot/FPL League History.csv"
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

async def daily_quiz_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная рассылка вопросов (заглушка, требует chat_id)."""
    logger.info("Daily quiz job executed (needs chat_id)")

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
        f"1. {league_q['question']}\n"
        f"2. {football_q['question']}\n\n"
        "Ответы отправляйте в формате: /answer 1 <ответ> и /answer 2 <ответ>"
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

# ========== Guess The Diff ==========

async def gtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать опрос GTD для текущего тура."""
    try:
        event = await get_current_event()
        if not event:
            await update.message.reply_text("Не удалось определить текущий тур.")
            return
        bs = await get_bootstrap_static()
        candidates = [p for p in bs["elements"] if p["selected_by_percent"] < 5]
        if len(candidates) < 10:
            await update.message.reply_text("Недостаточно игроков с ownership <5% для опроса.")
            return
        selected = random.sample(candidates, 10)
        context.bot_data[f"gtd_{event}"] = selected
        text = f"🔮 *Guess The Diff – тур {event}*\nКто из этих игроков забьёт гол? (выберите всех)"
        keyboard = []
        for p in selected:
            keyboard.append([InlineKeyboardButton(p["web_name"], callback_data=f"gtd_{event}_{p['id']}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data=f"gtd_{event}_done")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in gtd: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

async def gtd_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    if len(data) < 3:
        return
    event = int(data[1])
    if data[2] == "done":
        # Здесь можно сохранить прогнозы, пока оставим заглушку
        await query.edit_message_text("Прогнозы сохранены! Результаты появятся после тура.")
    else:
        player_id = int(data[2])
        # Временно просто подтверждаем выбор
        await query.edit_message_text(f"Вы выбрали игрока. (Заглушка)")

# ========== Чемпионат прогнозов ==========

async def predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать матчи тура для прогнозов (заглушка)."""
    await update.message.reply_text("Чемпионат прогнозов в разработке.")

# ========== Таблицы лидеров ==========

async def scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать общую таблицу лидеров."""
    try:
        scores = await get_scores()
        if not scores:
            await update.message.reply_text("Таблица лидеров пуста.")
            return
        text = "🏆 *Общая таблица лидеров*\n\n"
        for i, (user_id, score, total) in enumerate(scores[:10], 1):
            # Получаем имя пользователя? Пока используем user_id
            text += f"{i}. `{user_id}` – {score} очков (всего попыток: {total})\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in scoreboard: {e}")
        await update.message.reply_text("Ошибка получения таблицы.")

async def scoreboard_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game: str):
    """Показать таблицу по конкретной игре."""
    try:
        scores = await get_scores(game)
        if not scores:
            await update.message.reply_text(f"Таблица по игре {game} пуста.")
            return
        text = f"🏆 *Таблица {game}*\n\n"
        for i, (user_id, score, total) in enumerate(scores[:10], 1):
            text += f"{i}. `{user_id}` – {score} очков (всего попыток: {total})\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in scoreboard_game: {e}")
        await update.message.reply_text("Ошибка получения таблицы.")

# ========== Основная команда /fun ==========

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
    try:
        if data == "fun_dq":
            await dq(update, context)
        elif data == "fun_gtd":
            await gtd(update, context)
        elif data == "fun_predict":
            await predictions(update, context)
        elif data == "fun_scoreboard":
            keyboard = [
                [InlineKeyboardButton("DoubleQuiz", callback_data="score_dq")],
                [InlineKeyboardButton("Guess The Diff", callback_data="score_gtd")],
                [InlineKeyboardButton("Прогнозы", callback_data="score_predict")],
                [InlineKeyboardButton("Общий зачёт", callback_data="score_all")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_fun")],
            ]
            await query.edit_message_text("Выберите таблицу:", reply_markup=InlineKeyboardMarkup(keyboard))
        elif data.startswith("score_"):
            game_map = {
                "score_dq": "dq",
                "score_gtd": "gtd",
                "score_predict": "predict",
                "score_all": None
            }
            game = game_map.get(data)
            if game is None:
                await scoreboard(update, context)
            else:
                await scoreboard_game(update, context, game)
        elif data == "back_to_fun":
            await fun(update, context)
    except Exception as e:
        logger.error(f"Error in fun_callback: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте позже.")
