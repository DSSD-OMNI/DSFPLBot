"""
Раздел Other — настройки, информация о боте, статистика.
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from apps.dsfplbot.database import (
    get_notifications_enabled, set_notifications_enabled,
    get_deadline_reminders, set_deadline_reminders
)

logger = logging.getLogger(__name__)


async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню раздела Other."""
    keyboard = [
        [InlineKeyboardButton("⚙️ Настройки уведомлений", callback_data="other_notifications")],
        [InlineKeyboardButton("ℹ️ О боте и модели", callback_data="other_about")],
        [InlineKeyboardButton("📊 Статистика работы", callback_data="other_stats")],
        [InlineKeyboardButton("🔙 На главную", callback_data="back_to_main")],
    ]
    text = "⚙️ *Раздел настроек*\n\nВыберите пункт:"

    if update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def other_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback-кнопок раздела Other."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    try:
        if data == "other" or data == "other_":
            await other(update, context)

        elif data == "other_notifications":
            enabled = await get_notifications_enabled(user_id)
            reminders = await get_deadline_reminders(user_id)
            text = (
                f"⚙️ *Настройки уведомлений*\n\n"
                f"🔔 Уведомления о матчах (>3 очков): {'✅ вкл' if enabled else '❌ выкл'}\n"
                f"⏰ Напоминания о дедлайне: {'✅ вкл' if reminders else '❌ выкл'}\n"
            )
            keyboard = [
                [InlineKeyboardButton(
                    f"🔔 {'Выключить' if enabled else 'Включить'} матчи",
                    callback_data="notif_toggle"
                )],
                [InlineKeyboardButton(
                    f"⏰ {'Выключить' if reminders else 'Включить'} дедлайн",
                    callback_data="remind_toggle"
                )],
                [InlineKeyboardButton("🔙 Назад", callback_data="other")],
            ]
            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )

        elif data == "notif_toggle":
            enabled = await get_notifications_enabled(user_id)
            await set_notifications_enabled(user_id, not enabled)
            # Перерисовываем меню уведомлений
            query.data = "other_notifications"
            await other_callback(update, context)

        elif data == "remind_toggle":
            reminders = await get_deadline_reminders(user_id)
            await set_deadline_reminders(user_id, not reminders)
            query.data = "other_notifications"
            await other_callback(update, context)

        elif data == "other_about":
            text = (
                "🤖 *О DSFPLBot*\n\n"
                "DSFPLBot — интеллектуальный помощник для Fantasy Premier League, "
                "разработанный для лиги «les mutants».\n\n"
                "📊 *Модель DSSD*\n"
                "Основная метрика — *LRI (League Race Index)* — интегральный "
                "показатель от 1 до 10, отражающий шансы на победу в лиге. "
                "Рассчитывается на основе 21 фактора (xG, xA, форма, Elo "
                "соперников, трансферы, чипы и др.).\n\n"
                "🔧 *Команды:*\n"
                "/afterdl — отчёт после дедлайна\n"
                "/aftertour — итоги тура\n"
                "/dssdtempo — таблица + темп + LRI\n"
                "/dssdadvice — персональные рекомендации\n"
                "/fun — игры\n"
                "/halloffame — зал славы\n"
                "/link — привязка FPL ID\n\n"
                "Создано: Daniil Sergeevich & Ivan Tiron"
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="other")]]
            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )

        elif data == "other_stats":
            # Получаем информацию о парсере
            try:
                from apps.dsfplbot.fpl_data_reader import get_parser_tables
                tables = await get_parser_tables()
                tables_text = ", ".join(tables[:10]) if tables else "нет данных"
            except Exception:
                tables_text = "недоступно"

            text = (
                "📊 *Статистика работы*\n\n"
                f"🗄 Таблицы парсера: {tables_text}\n\n"
                "Расширенная статистика в разработке."
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="other")]]
            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )

        elif data == "back_to_main":
            from apps.dsfplbot.handlers import start
            await start(update, context)

    except Exception as e:
        logger.error(f"Error in other_callback ({data}): {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ Ошибка. Попробуйте позже.")
        except Exception:
            pass
