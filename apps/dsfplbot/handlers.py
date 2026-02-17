import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

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
    await update.message.reply_text("afterdl – заглушка")

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
