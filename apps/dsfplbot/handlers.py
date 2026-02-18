"""
Обработчики команд DSFPLBot.
"""
import logging
from datetime import datetime

import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from apps.dsfplbot.config import FPL_LEAGUE_ID, ADMIN_USER_ID
from apps.dsfplbot.fpl_api import get_current_event, get_event_deadline, is_event_finished

logger = logging.getLogger(__name__)

# Состояния ConversationHandler
WEEKS = 1
LINK_FPL = 2


# ────────────────────────────────────────────────────────────────────
# /start
# ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и список команд."""
    # Получаем актуальный дедлайн из FPL API
    deadline_text = ""
    try:
        event = await get_current_event()
        if event:
            deadline_dt = await get_event_deadline(event)
            if deadline_dt:
                now = datetime.now(pytz.UTC)
                if now < deadline_dt:
                    diff = deadline_dt - now
                    days = diff.days
                    hours = diff.seconds // 3600
                    minutes = (diff.seconds % 3600) // 60
                    deadline_text = f"⏳ До дедлайна GW{event}: {days}д {hours}ч {minutes}м\n\n"
                else:
                    deadline_text = f"⏳ Дедлайн GW{event} прошёл!\n\n"
    except Exception as e:
        logger.debug(f"Could not get deadline: {e}")

    commands_text = (
        "👋 *Добро пожаловать в DSFPLBot!*\n\n"
        f"{deadline_text}"
        "*Доступные команды:*\n"
        "/start — приветствие\n"
        "/afterdl — отчёт после дедлайна тура\n"
        "/aftertour — итоги завершённого тура\n"
        "/dssdtempo — таблица лиги + темп + LRI\n"
        "/dssdadvice — персональные рекомендации (ЛС)\n"
        "/fun — Mutantos Game Arena\n"
        "/halloffame — зал славы лиги\n"
        "/other — настройки и информация\n"
        "/link — привязать FPL ID\n"
        "/cancel — отменить операцию\n"
    )
    msg = update.message or update.callback_query.message
    if update.message:
        await update.message.reply_text(commands_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(commands_text, parse_mode="Markdown")


# ────────────────────────────────────────────────────────────────────
# /link — привязка FPL ID
# ────────────────────────────────────────────────────────────────────

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 Введите ваш FPL ID (число из URL вашей команды) или /cancel для отмены."
    )
    return LINK_FPL


async def link_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите целое число.")
        return LINK_FPL

    fpl_id = int(text)
    try:
        from apps.dsfplbot.database import save_user_fpl_id
        await save_user_fpl_id(update.effective_user.id, fpl_id)
        await update.message.reply_text(f"✅ FPL ID {fpl_id} успешно привязан!")
    except Exception as e:
        logger.error(f"Error saving FPL ID: {e}")
        await update.message.reply_text(
            "❌ Ошибка при сохранении. Попробуйте позже."
        )
    return ConversationHandler.END


async def link_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привязка отменена.")
    return ConversationHandler.END


# ────────────────────────────────────────────────────────────────────
# /afterdl — отчёт после дедлайна
# ────────────────────────────────────────────────────────────────────

async def afterdl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event = await get_current_event()
    if not event:
        await update.message.reply_text("❌ Не удалось определить текущий тур.")
        return

    deadline = await get_event_deadline(event)
    if deadline:
        now = datetime.now(pytz.UTC)
        if now < deadline:
            diff = deadline - now
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60
            await update.message.reply_text(
                f"⏳ Отчёт будет доступен после дедлайна. "
                f"Осталось: {diff.days}д {hours}ч {minutes}м"
            )
            return

    await update.message.reply_text("🔍 Собираю данные после дедлайна...")
    try:
        from apps.dsfplbot.afterdl import collect_afterdl_data, format_afterdl_report
        data = await collect_afterdl_data(FPL_LEAGUE_ID, event)
        report = format_afterdl_report(data)
        # Telegram ограничивает сообщения 4096 символами
        if len(report) > 4000:
            parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in afterdl: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при сборе данных. Парсер, возможно, ещё не заполнил базу.\n"
            "Попробуйте позже."
        )


# ────────────────────────────────────────────────────────────────────
# /aftertour — итоги завершённого тура
# ────────────────────────────────────────────────────────────────────

async def aftertour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event = await get_current_event()
    if not event:
        await update.message.reply_text("❌ Не удалось определить текущий тур.")
        return

    if not await is_event_finished(event):
        await update.message.reply_text(
            "⏳ Тур ещё не завершён. Отчёт будет после окончания всех матчей."
        )
        return

    await update.message.reply_text("🔍 Собираю итоги тура...")
    try:
        from apps.dsfplbot.aftertour import collect_aftertour_data, format_aftertour_report
        data = await collect_aftertour_data(FPL_LEAGUE_ID, event)
        report = format_aftertour_report(data)
        if len(report) > 4000:
            parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in aftertour: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при сборе данных. Попробуйте позже.")


# ────────────────────────────────────────────────────────────────────
# /dssdtempo — таблица лиги + темп + LRI
# ────────────────────────────────────────────────────────────────────

async def dssdtempo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *Расчёт темпа*\n\n"
        "За сколько последних туров рассчитать темп? (минимум 2)",
        parse_mode="Markdown"
    )
    return WEEKS


async def dssdtempo_get_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введённого числа и вывод таблицы с реальными данными из БД парсера."""
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Введите целое число.")
        return WEEKS

    weeks = int(text)
    if weeks < 2:
        await update.message.reply_text("Минимум 2 тура.")
        return WEEKS

    try:
        from apps.dsfplbot.fpl_data_reader import (
            get_latest_league_standings, get_manager_history,
            get_latest_lri_for_entry, get_form_for_entry,
            get_current_event_from_parser
        )
        from apps.dsfplbot.dssd import generate_personalized_advice

        # Получаем текущий тур
        current_event = await get_current_event()
        if not current_event:
            from apps.dsfplbot.fpl_data_reader import get_current_event_from_parser
            current_event = await get_current_event_from_parser()

        # Получаем таблицу лиги
        standings = await get_latest_league_standings(FPL_LEAGUE_ID)
        if not standings:
            await update.message.reply_text(
                "📊 Данные лиги ещё не загружены парсером. Попробуйте позже."
            )
            return ConversationHandler.END

        # Для каждого менеджера получаем LRI и темп
        for s in standings:
            entry_id = s.get("entry_id")

            # LRI из парсера
            lri = await get_latest_lri_for_entry(entry_id) if entry_id else None
            s["lri"] = lri if lri is not None else 5.0

            # Темп: пробуем из manager_history, fallback на form_5gw
            if entry_id:
                history = await get_manager_history(entry_id)
                if history and current_event:
                    recent = [h for h in history if h.get("event", 0) <= current_event]
                    recent = recent[-weeks:]  # последние N туров
                    if recent:
                        points_list = [h.get("points", h.get("event_points", 0)) for h in recent]
                        s["form"] = sum(points_list) / len(points_list) if points_list else 0
                        s["games_played"] = len(recent)
                    else:
                        s["form"] = 0
                        s["games_played"] = 0
                else:
                    # Fallback: form_5gw из features
                    form = await get_form_for_entry(entry_id)
                    s["form"] = form if form is not None else 0
                    s["games_played"] = 5 if form else 0
            else:
                s["form"] = 0
                s["games_played"] = 0

        # Определяем, использовался ли fallback
        has_history = any(s.get("games_played", 0) > 0 and s["games_played"] != 5
                         for s in standings)
        form_source = f"за {weeks} тур." if has_history else "за 5 тур. (form\\_5gw)"

        # Формируем таблицу
        lines = [f"📊 *Таблица лиги «les mutants»*\n_Темп {form_source}_\n"]
        lines.append("```")
        lines.append(f"{'#':<3}{'Менеджер':<14}{'Очки':<6}{'Темп':<6}{'LRI':<5}")
        lines.append("─" * 34)

        for s in standings:
            rank = s.get("rank", s.get("last_rank", "?"))
            name = s.get("player_name", s.get("entry_name", "?"))[:13]
            total = s.get("total", s.get("total_points", s.get("event_total", 0)))
            form = s.get("form", 0)
            lri = s.get("lri", 5.0)
            lines.append(f"{rank:<3}{name:<14}{total:<6}{form:<6.1f}{lri:<5.1f}")

        lines.append("```")

        # Советы
        advice = generate_personalized_advice(standings, weeks)
        if advice:
            lines.append(f"\n💡 *Советы:*\n{advice}")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in dssdtempo_get_weeks: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Не удалось получить данные. Убедитесь, что парсер запущен."
        )

    return ConversationHandler.END


async def dssdtempo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ────────────────────────────────────────────────────────────────────
# /dssdadvice — персональные рекомендации
# ────────────────────────────────────────────────────────────────────

async def dssdadvice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Генерирую рекомендации...")
    try:
        from apps.dsfplbot.dssd_advice import generate_advice
        event = await get_current_event()
        advice = await generate_advice(
            update.effective_user.id, FPL_LEAGUE_ID, event
        )
        # Отправляем в ЛС
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=advice,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in dssdadvice: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при генерации рекомендаций. "
            "Убедитесь, что FPL ID привязан (/link)."
        )


# ────────────────────────────────────────────────────────────────────
# /export_data — экспорт БД (только для админа)
# ────────────────────────────────────────────────────────────────────

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    import zipfile
    import os
    from apps.dsfplbot.config import DB_PATH, FPL_PARSER_DB_PATH

    zip_path = "/tmp/backup.zip"
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for path in [DB_PATH, FPL_PARSER_DB_PATH]:
                if os.path.exists(path):
                    zipf.write(path, os.path.basename(path))
        with open(zip_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_user.id, document=f,
                filename="dsfplbot_backup.zip"
            )
    except Exception as e:
        logger.error(f"Export error: {e}")
        await update.message.reply_text(f"❌ Ошибка экспорта: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
