import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from apps.dsfplbot.config import FPL_LEAGUE_ID
from apps.dsfplbot.utils import time_until_deadline
from apps.dsfplbot.fpl_api import get_current_event, get_event_deadline, is_event_finished
from apps.dsfplbot.afterdl import collect_afterdl_data, format_afterdl_report

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
    if data == "menu_afterdl":
        await afterdl(update, context)
    elif data == "menu_aftertour":
        await aftertour(update, context)
    elif data == "menu_dssdtempo":
        await dssdtempo_start(update, context)
    elif data == "menu_dssdadvice":
        await dssdadvice(update, context)
    elif data == "menu_fun":
        await fun(update, context)
    elif data == "menu_halloffame":
        from apps.dsfplbot.halloffame import halloffame
        await halloffame(update, context)
    elif data == "menu_other":
        from apps.dsfplbot.other import other
        await other(update, context)
    elif data == "menu_link":
        await link_start(update, context)
    elif data == "back_to_main":
        await start(update, context)

# ---------- AFTERDL (реальная) ----------
async def afterdl(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        data = await collect_afterdl_data(FPL_LEAGUE_ID, event)
        report = format_afterdl_report(data)
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в afterdl: {e}")
        await update.message.reply_text("❌ Данные для отчёта ещё не собраны. Убедитесь, что парсер запущен.")

# ---------- ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ КОМАНД ----------
async def aftertour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("aftertour – заглушка")

async def dssdtempo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("dssdtempo_start – заглушка")
    return WEEKS

async def dssdtempo_get_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("dssdtempo_get_weeks – заглушка")
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
    await update.message.reply_text("link_get_id – заглушка")
    return ConversationHandler.END

async def link_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("link_cancel – заглушка")
    return ConversationHandler.END

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("export_data – заглушка")

async def fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("fun – заглушка")
