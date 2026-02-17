import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

WEEKS = 1
LINK_FPL = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_text = (
        "👋 *Добро пожаловать в DSFPLBot!*\n\n"
        "⏳ До дедлайна: 4д 17ч 38м\n\n"
        "*Доступные команды:*\n"
        "/start - приветствие и список команд\n"
        "/afterdl - отчёт после дедлайна тура\n"
        "/aftertour - итоги завершённого тура\n"
        "/dssdtempo - таблица лиги + темп + LRI\n"
        "/dssdadvice - персональные трансферные советы\n"
        "/fun - Mutantos Game Arena (игры)\n"
        "/halloffame - зал славы лиги FPL и Мутантов\n"
        "/other - настройки и информация о боте\n"
        "/link - привязать свой FPL ID\n"
        "/cancel - отменить текущую операцию\n"
    )
    await update.message.reply_text(commands_text, parse_mode="Markdown")

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваш FPL ID (число) или /cancel для отмены.")
    return LINK_FPL

async def link_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите целое число.")
        return LINK_FPL
    fpl_id = int(text)
    from apps.dsfplbot.database import save_user_fpl_id
    await save_user_fpl_id(update.effective_user.id, fpl_id)
    await update.message.reply_text(f"✅ FPL ID {fpl_id} успешно привязан!")
    return ConversationHandler.END

async def link_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привязка отменена.")
    return ConversationHandler.END

async def afterdl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.fpl_api import get_current_event, get_event_deadline
    import pytz
    event = await get_current_event()
    if not event:
        await update.message.reply_text("❌ Не удалось определить текущий тур.")
        return
    deadline = await get_event_deadline(event)
    now = datetime.now(pytz.UTC)
    if now < deadline:
        diff = deadline - now
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        await update.message.reply_text(f"⏳ Отчёт будет доступен после дедлайна. Осталось: {hours} ч {minutes} мин.")
        return
    await update.message.reply_text("🔍 Собираю данные после дедлайна... Это может занять некоторое время.")
    try:
        from apps.dsfplbot.afterdl import collect_afterdl_data, format_afterdl_report
        data = await collect_afterdl_data(FPL_LEAGUE_ID, event)
        report = format_afterdl_report(data)
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка в afterdl: {e}")
        await update.message.reply_text("❌ Данные для отчёта ещё не собраны. Убедитесь, что парсер запущен.")

async def aftertour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.fpl_api import get_current_event, is_event_finished
    event = await get_current_event()
    if not event:
        await update.message.reply_text("❌ Не удалось определить текущий тур.")
        return
    if not await is_event_finished(event):
        await update.message.reply_text("⏳ Тур ещё не завершён. Отчёт будет после окончания всех матчей.")
        return
    try:
        from apps.dsfplbot.aftertour import collect_aftertour_data, format_aftertour_report
        data = await collect_aftertour_data(FPL_LEAGUE_ID, event)
        report = format_aftertour_report(data)
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка в aftertour: {e}")
        await update.message.reply_text("❌ Данные для отчёта ещё не собраны. Убедитесь, что парсер запущен.")

async def dssdtempo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *Расчёт темпа*\n\nЗа сколько последних туров рассчитать темп? (минимум 2)",
        parse_mode="Markdown"
    )
    return WEEKS

async def dssdtempo_get_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Введите целое число.")
        return WEEKS
    weeks = int(text)
    if weeks < 2:
        await update.message.reply_text("Минимум 2 тура.")
        return WEEKS

    from apps.dsfplbot.fpl_data_reader import get_latest_league_standings, get_manager_history
    from apps.dsfplbot.fpl_api import get_current_event
    from apps.dsfplbot.dssd import generate_personalized_advice
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)

    try:
        current_event = await get_current_event()
        standings = await get_latest_league_standings(FPL_LEAGUE_ID)
        if not standings:
            await update.message.reply_text(
                "📊 Данные лиги ещё не загружены. Парсер работает, попробуйте позже.\n"
                "Если парсер отключён, эта команда недоступна."
            )
            return ConversationHandler.END

        for s in standings:
            history = await get_manager_history(s["entry_id"])
            if history:
                recent = [h for h in history if h["event"] <= current_event][-weeks:]
                if recent:
                    s["form"] = sum(h["points"] for h in recent) / len(recent)
                    s["games_played"] = len(recent)
                else:
                    s["form"] = 0
                    s["games_played"] = 0
            else:
                s["form"] = 0
                s["games_played"] = 0

        lines = [f"📊 *Текущая таблица лиги* (темп за последние {weeks} туров)\n"]
        lines.append("```")
        lines.append("#  Менеджер        Очки  Темп   LRI")
        lines.append("-" * 50)
        for s in standings:
            name = s.get("manager_name", "Unknown")[:12]
            lri = 5.0  # заглушка
            lines.append(f"{s['rank']:<2} {name:12} {s['total_points']:<5} {s['form']:<5.1f} {lri:<4.1f}")
        lines.append("```")

        advice = generate_personalized_advice(standings, weeks)
        if advice:
            lines.append("\n💡 *Советы*\n" + advice)

        keyboard = [
            [InlineKeyboardButton("🔮 Прогноз", callback_data="dssd_forecast")],
            [InlineKeyboardButton("📈 С лидером", callback_data="dssd_compare")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="dssd_refresh")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("\n".join(lines), reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в dssdtempo_get_weeks: {e}")
        await update.message.reply_text(f"❌ Произошла внутренняя ошибка. Пожалуйста, попробуйте позже.")
    return ConversationHandler.END

async def dssdtempo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def dssdadvice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.dssd_advice import generate_advice
    from apps.dsfplbot.fpl_api import get_current_event
    await update.message.reply_text("⏳ Генерирую рекомендации... Они придут в личные сообщения.")
    advice = await generate_advice(update.effective_user.id, FPL_LEAGUE_ID, await get_current_event())
    await context.bot.send_message(chat_id=update.effective_user.id, text=advice, parse_mode="Markdown")

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.config import ADMIN_USER_ID
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    import zipfile, os
    zip_path = "backup.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write("dsfpl.db")
        zipf.write("fpl_data.db")
        zipf.write("bot.log")
        zipf.write("fpl_parser.log")
    with open(zip_path, 'rb') as f:
        await context.bot.send_document(chat_id=update.effective_user.id, document=f)
    os.remove(zip_path)
