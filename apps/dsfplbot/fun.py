"""
Mutantos Game Arena — DoubleQuiz, GuessTheDiff, прогнозы, таблицы.
"""
import random
import re
import os
import logging
from datetime import date
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from apps.dsfplbot.database import add_score, get_scores
from apps.dsfplbot.fpl_api import get_bootstrap_static, get_current_event

logger = logging.getLogger(__name__)

# Кэш загруженных вопросов
_football_questions: Optional[List[Dict[str, str]]] = None


def _load_questions_from_text(filepath: str) -> List[Dict[str, str]]:
    """
    Парсит файл questions.json (на самом деле текстовый формат):
    Вопрос N. <текст вопроса>

    Ответ: <ответ> .
    """
    questions = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Ищем пары "Вопрос N. ... Ответ: ..."
        pattern = r"Вопрос\s+\d+\.\s*(.*?)\n\s*\n\s*Ответ:\s*(.*?)(?:\s*\.?\s*$|\n)"
        matches = re.findall(pattern, content, re.MULTILINE)

        for q_text, a_text in matches:
            q_text = q_text.strip()
            a_text = a_text.strip().rstrip(".")
            # Убираем кавычки-ёлочки из ответа для удобства сравнения
            a_clean = a_text.replace("«", "").replace("»", "").strip()
            if q_text and a_clean:
                questions.append({"question": q_text, "answer": a_clean})

        logger.info(f"Loaded {len(questions)} football questions")
    except FileNotFoundError:
        logger.warning(f"Questions file not found: {filepath}")
    except Exception as e:
        logger.error(f"Error loading questions: {e}")

    return questions


def _get_football_questions() -> List[Dict[str, str]]:
    """Возвращает список футбольных вопросов (с кэшированием)."""
    global _football_questions
    if _football_questions is None:
        questions_path = os.path.join(os.path.dirname(__file__), "questions.json")
        _football_questions = _load_questions_from_text(questions_path)
        if not _football_questions:
            _football_questions = [
                {"question": "Кто выиграл ЧМ-2018?", "answer": "Франция"},
                {"question": "Кто выиграл ЛЧ в 2005 году?", "answer": "Ливерпуль"},
            ]
    return _football_questions


async def _generate_league_question() -> Dict[str, str]:
    """Генерирует вопрос по истории лиги из CSV."""
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), "FPL League History.csv")
    try:
        if not os.path.exists(csv_path):
            return {"question": "Кто выиграл лигу в сезоне 2023/24?", "answer": "Peter Popov"}

        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if not rows:
                return {"question": "Кто выиграл лигу?", "answer": "Unknown"}

            # Выбираем случайную запись с pos=1 (победитель)
            winners = [r for r in rows if str(r.get("Pos", "")).strip() == "1"]
            if not winners:
                winners = rows
            row = random.choice(winners)
            season = row["Season"]
            manager = row["Manager"]
            return {
                "question": f"Кто занял 1-е место в лиге в сезоне {season}?",
                "answer": manager
            }
    except Exception as e:
        logger.error(f"Error generating league question: {e}")
        return {"question": "Кто выиграл лигу в сезоне 2019/20?", "answer": "Peter Popov"}


# ────────────────────────────────────────────────────────────────────
# Ежедневный квиз (job)
# ────────────────────────────────────────────────────────────────────

async def daily_quiz_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная задача. Пока только логирование (нужен chat_id для рассылки)."""
    logger.info("Daily quiz job executed (needs target chat_id for broadcast)")


# ────────────────────────────────────────────────────────────────────
# /dq — DoubleQuiz
# ────────────────────────────────────────────────────────────────────

async def dq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сегодняшние вопросы DoubleQuiz."""
    today = date.today().isoformat()

    league_q = await _generate_league_question()
    football_qs = _get_football_questions()
    football_q = random.choice(football_qs)

    context.bot_data[f"quiz_{today}"] = {"q1": league_q, "q2": football_q}

    text = (
        f"🎯 *DoubleQuiz на {today}*\n\n"
        f"1️⃣ {league_q['question']}\n\n"
        f"2️⃣ {football_q['question']}\n\n"
        "Ответы: `/answer 1 ваш ответ` и `/answer 2 ваш ответ`"
    )

    msg = update.message or update.callback_query.message
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")


# ────────────────────────────────────────────────────────────────────
# /answer — ответ на вопрос
# ────────────────────────────────────────────────────────────────────

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа /answer <номер> <ответ>."""
    try:
        args = context.args
        if not args or len(args) < 2:
            await update.message.reply_text("Использование: `/answer 1 ваш ответ`", parse_mode="Markdown")
            return

        q_num = int(args[0])
        user_answer = " ".join(args[1:]).strip().lower()
        # Нормализуем: убираем кавычки
        user_answer = user_answer.replace("«", "").replace("»", "").replace('"', '').replace("'", "")

        today = date.today().isoformat()
        quiz_key = f"quiz_{today}"

        if quiz_key not in context.bot_data:
            await update.message.reply_text(
                "На сегодня вопросы ещё не заданы. Введите /dq"
            )
            return

        quiz = context.bot_data[quiz_key]

        if q_num == 1:
            correct = quiz["q1"]["answer"].lower()
        elif q_num == 2:
            correct = quiz["q2"]["answer"].lower()
        else:
            await update.message.reply_text("Номер вопроса: 1 или 2.")
            return

        # Нормализуем правильный ответ
        correct_norm = correct.replace("«", "").replace("»", "").replace('"', '').replace("'", "")

        if user_answer == correct_norm or correct_norm in user_answer:
            await add_score(update.effective_user.id, "dq", 1)
            await update.message.reply_text("✅ Правильно! +1 очко.")
        else:
            await update.message.reply_text(f"❌ Неправильно. Правильный ответ: {quiz[f'q{q_num}']['answer']}")

    except (ValueError, IndexError):
        await update.message.reply_text("Использование: `/answer 1 ваш ответ`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in answer: {e}")
        await update.message.reply_text("Ошибка обработки ответа.")


# ────────────────────────────────────────────────────────────────────
# /gtd — Guess The Diff
# ────────────────────────────────────────────────────────────────────

async def gtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Опрос GTD: угадай, кто из малоизвестных игроков забьёт."""
    try:
        event = await get_current_event()
        if not event:
            msg = update.message or update.callback_query.message
            await msg.reply_text("Не удалось определить текущий тур.")
            return

        bs = await get_bootstrap_static()
        if not bs:
            msg = update.message or update.callback_query.message
            await msg.reply_text("Не удалось получить данные FPL.")
            return

        candidates = [p for p in bs["elements"]
                       if float(p.get("selected_by_percent", 100)) < 5
                       and p.get("minutes", 0) > 0]

        if len(candidates) < 10:
            msg = update.message or update.callback_query.message
            await msg.reply_text("Недостаточно игроков для опроса.")
            return

        selected = random.sample(candidates, min(10, len(candidates)))
        context.bot_data[f"gtd_{event}"] = selected

        text = f"🔮 *Guess The Diff — GW{event}*\nКто из этих игроков забьёт? (выберите)"
        keyboard = []
        for p in selected:
            keyboard.append([
                InlineKeyboardButton(
                    p["web_name"],
                    callback_data=f"gtd_{event}_{p['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data=f"gtd_{event}_done")])

        msg = update.message or update.callback_query.message
        if update.message:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in gtd: {e}")
        msg = update.message or update.callback_query.message
        if msg:
            await msg.reply_text("Произошла ошибка. Попробуйте позже.")


# ────────────────────────────────────────────────────────────────────
# /predictions — чемпионат прогнозов
# ────────────────────────────────────────────────────────────────────

async def predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    text = "🏟 *Чемпионат прогнозов* — в разработке.\n\nСледите за обновлениями!"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")


# ────────────────────────────────────────────────────────────────────
# /scoreboard — таблица лидеров
# ────────────────────────────────────────────────────────────────────

async def scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        scores = await get_scores()
        if not scores:
            text = "🏆 Таблица лидеров пуста. Начните играть!"
        else:
            text = "🏆 *Общая таблица лидеров*\n\n"
            for i, (user_id, score, total) in enumerate(scores[:10], 1):
                text += f"{i}. `{user_id}` — {score} очков ({total} попыток)\n"

        msg = update.message or update.callback_query.message
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in scoreboard: {e}")


async def _scoreboard_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game: str):
    """Таблица по конкретной игре."""
    try:
        scores = await get_scores(game)
        if not scores:
            text = f"🏆 Таблица *{game}* пуста."
        else:
            text = f"🏆 *Таблица {game}*\n\n"
            for i, (user_id, score, total) in enumerate(scores[:10], 1):
                text += f"{i}. `{user_id}` — {score} очков ({total} попыток)\n"

        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in scoreboard_game: {e}")


# ────────────────────────────────────────────────────────────────────
# /fun — главное меню игр
# ────────────────────────────────────────────────────────────────────

async def fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 DoubleQuiz", callback_data="fun_dq")],
        [InlineKeyboardButton("🔮 Guess The Diff", callback_data="fun_gtd")],
        [InlineKeyboardButton("🏟 Чемпионат прогнозов", callback_data="fun_predict")],
        [InlineKeyboardButton("🏆 Таблицы", callback_data="fun_scoreboard")],
    ]
    text = "🎮 *Mutantos Game Arena*\n\nВыберите игру:"

    if update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def fun_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback-кнопок раздела Fun."""
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
                [InlineKeyboardButton("🎯 DoubleQuiz", callback_data="score_dq")],
                [InlineKeyboardButton("🔮 Guess The Diff", callback_data="score_gtd")],
                [InlineKeyboardButton("🏟 Прогнозы", callback_data="score_predict")],
                [InlineKeyboardButton("📊 Общий зачёт", callback_data="score_all")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_fun")],
            ]
            await query.edit_message_text(
                "🏆 *Выберите таблицу:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif data.startswith("score_"):
            game_map = {"score_dq": "dq", "score_gtd": "gtd",
                        "score_predict": "predict", "score_all": None}
            game = game_map.get(data)
            if game is None:
                await scoreboard(update, context)
            else:
                await _scoreboard_game(update, context, game)

        elif data == "back_to_fun":
            await fun(update, context)

        elif data.startswith("gtd_"):
            parts = data.split("_")
            if len(parts) >= 3 and parts[2] == "done":
                await query.edit_message_text("✅ Прогнозы сохранены! Результаты появятся после тура.")
            elif len(parts) >= 3:
                # Сохранение выбора (пока упрощённо)
                await query.answer("Выбор сохранён ✓", show_alert=False)

    except Exception as e:
        logger.error(f"Error in fun_callback: {e}", exc_info=True)
        try:
            await query.edit_message_text("Произошла ошибка. Попробуйте позже.")
        except Exception:
            pass
