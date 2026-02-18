import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
    ConversationHandler,\
logger = logging.getLogger(__name__)
WEEKS = 1
LINK_FPL = 2

# ---------- МЕНЮ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Post-Deadline Report", callback_data="menu_afterdl")],
        [InlineKeyboardButton("📊 GW Summary", callback_data="menu_aftertour")],
        [InlineKeyboardButton("📈 Table + Pace + LRI", callback_data="menu_dssdtempo")],
        [InlineKeyboardButton("🎯 AI Advice", callback_data="menu_dssdadvice")],
        [InlineKeyboardButton("🎮 Fun Zone", callback_data="menu_fun")],
        [InlineKeyboardButton("🏆 Hall of Fame", callback_data="menu_halloffame")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_other")],
        [InlineKeyboardButton("🔗 Link FPL ID", callback_data="menu_link")],
    ]
    await update.message.reply_text(
        "👋 *DSFPLBot v2 – Menu*\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    await query.edit_message_text(f"Выбрано: {data} (заглушка)")

# ---------- ЗАГЛУШКИ ДЛЯ ВСЕХ КОМАНД ----------
async def afterdl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.fpl_data_reader import get_latest_league_standings, get_lri_for_entry
    from apps.dsfplbot.fpl_api import get_current_event
    import logging
    logger = logging.getLogger(__name__)
    try:
        current_event = await get_current_event()
        standings = await get_latest_league_standings(FPL_LEAGUE_ID)
        if not standings:
            await update.message.reply_text("📊 Данные лиги ещё не загружены.")
            return
        lines = ["📋 *Отчёт после дедлайна (упрощённо)*\n"]
        for s in standings:
            lri = await get_lri_for_entry(s["entry_id"], current_event)
            lines.append(f"• *{s['player_name']}* — {s['total_points']} pts (LRI: {lri:.1f})")
        lines.append("\n_Полная статистика появится позже._")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в afterdl: {e}")
        await update.message.reply_text("❌ Ошибка получения данных.")

async def aftertour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from apps.dsfplbot.fpl_data_reader import get_latest_league_standings, get_lri_for_entry
    from apps.dsfplbot.fpl_api import get_current_event
    import logging
    logger = logging.getLogger(__name__)
    try:
        current_event = await get_current_event()
        standings = await get_latest_league_standings(FPL_LEAGUE_ID)
        if not standings:
            await update.message.reply_text("📊 Данные лиги ещё не загружены.")
            return
        lines = ["📊 *Итоги тура (упрощённо)*\n"]
        # Сортируем по event_points, чтобы показать лучших
        sorted_by_event = sorted(standings, key=lambda x: x.get("event_points", 0), reverse=True)
        lines.append("🏆 *Лучшие в туре:*")
        for i, s in enumerate(sorted_by_event[:3]):
            lines.append(f"{i+1}. {s['player_name']} — {s.get('event_points', 0)} pts")
        lines.append("\n📈 *Текущая таблица:*")
        for s in standings[:5]:  # топ-5
            lri = await get_lri_for_entry(s["entry_id"], current_event)
            lines.append(f"{s['rank']}. {s['player_name']} — {s['total_points']} pts (LRI: {lri:.1f})")
        lines.append("\n_Детальная статистика появится позже._")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в aftertour: {e}")
        await update.message.reply_text("❌ Ошибка получения данных.")

async def dssdtempo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("dssdtempo_start – заглушка")
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

    from apps.dsfplbot.fpl_data_reader import get_latest_league_standings, get_lri_for_entry, get_form_for_entry
    from apps.dsfplbot.fpl_api import get_current_event
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)

    try:
        current_event = await get_current_event()
        standings = await get_latest_league_standings(FPL_LEAGUE_ID)
        if not standings:
            await update.message.reply_text("📊 Данные лиги ещё не загружены. Попробуйте позже.")
            return ConversationHandler.END

        for s in standings:
            s["lri"] = await get_lri_for_entry(s["entry_id"], current_event)
            # Пока используем form_5gw как темп (за 5 туров), в будущем заменим на историю
            s["form"] = await get_form_for_entry(s["entry_id"])

        lines = [f"📊 *Текущая таблица лиги* (темп за последние {weeks} туров)\n"]
        lines.append("```")
        lines.append("#  Менеджер        Очки  Темп   LRI")
        lines.append("-" * 50)
        for s in standings:
            name = s.get("player_name", "Unknown")[:12]
            lines.append(f"{s['rank']:<2} {name:12} {s['total_points']:<5} {s['form']:<5.1f} {s['lri']:<4.1f}")
        lines.append("```")

        # Советы пока отключены (заглушка)
        lines.append("\n💡 *Советы* временно отключены.")

        keyboard = [
            [InlineKeyboardButton("🔮 Прогноз", callback_data="dssd_forecast")],
            [InlineKeyboardButton("📈 С лидером", callback_data="dssd_compare")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="dssd_refresh")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("\n".join(lines), reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в dssdtempo_get_weeks: {e}")
        await update.message.reply_text("❌ Произошла внутренняя ошибка. Попробуйте позже.")
    return ConversationHandler.END

async def dssdtempo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def dssdadvice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("dssdadvice – заглушка")

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите FPL ID:")
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
    await update.message.reply_text("link_cancel – заглушка")
    return ConversationHandler.END

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("export_data – заглушка")

async def fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("fun – заглушка")
