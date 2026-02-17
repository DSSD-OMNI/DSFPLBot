from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.dsfplbot.database import get_notifications_enabled, set_notifications_enabled, get_deadline_reminders, set_deadline_reminders
import logging

logger = logging.getLogger(__name__)

async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚙️ Настройки уведомлений", callback_data="other_notifications")],
        [InlineKeyboardButton("ℹ️ О боте и модели", callback_data="other_about")],
        [InlineKeyboardButton("📊 Статистика работы", callback_data="other_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")],
    ]
    await update.message.reply_text(
        "⚙️ *Раздел Other*\n\nВыберите интересующий пункт:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def other_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "other_notifications":
        enabled = await get_notifications_enabled(user_id)
        reminders = await get_deadline_reminders(user_id)
        text = (
            f"⚙️ *Настройки уведомлений*\n\n"
            f"🔔 Уведомления о матчах (>3 очков): {'✅ включены' if enabled else '❌ отключены'}\n"
            f"⏰ Напоминания о дедлайне: {'✅ включены' if reminders else '❌ отключены'}\n\n"
            "Используйте кнопки ниже для изменения."
        )
        keyboard = [
            [InlineKeyboardButton(f"🔔 {'Выключить' if enabled else 'Включить'} матчи", callback_data="notif_toggle")],
            [InlineKeyboardButton(f"⏰ {'Выключить' if reminders else 'Включить'} дедлайн", callback_data="remind_toggle")],
            [InlineKeyboardButton("🔙 Назад", callback_data="other")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "notif_toggle":
        enabled = await get_notifications_enabled(user_id)
        await set_notifications_enabled(user_id, not enabled)
        await other_callback(update, context)  # обновляем меню

    elif data == "remind_toggle":
        reminders = await get_deadline_reminders(user_id)
        await set_deadline_reminders(user_id, not reminders)
        await other_callback(update, context)

    elif data == "other_about":
        text = (
            "🤖 *О DSFPLBot*\n\n"
            "DSFPLBot — интеллектуальный помощник для Fantasy Premier League, "
            "разработанный специально для лиги «Мутанты». Бот объединяет глубокую аналитику "
            "на основе модели DSSD, развлекательные мини-игры и удобные уведомления.\n\n"
            "📊 *Модель DSSD (Data. Strategy. Suspense. Drive.)*\n"
            "Прогностическая модель, созданная для анализа и прогнозирования результатов менеджеров. "
            "Основная метрика — **DSID League Race Index (LRI)** — интегральный показатель от 1 до 10, "
            "отражающий реальные шансы на победу в лиге. LRI рассчитывается на основе **21 фактора**, "
            "разделённых на три уровня:\n"
            "• *Уровень A* (7 базовых характеристик игрока: xG, xA, форма, минуты, ICT, бонусы, выбран %)\n"
            "• *Уровень B* (7 контекстных факторов: Elo соперника, домашний матч, сложность календаря, тренды команд)\n"
            "• *Уровень C* (7 динамических метрик: трансферы, волатильность, разнообразие капитанов, использование чипов, CBIT, non-penalty xG)\n\n"
            "Модель калибрована на 10 000 реальных и синтетических лиг, точность попадания в топ-3 — до 87%. "
            "LRI используется в разделах `/dssdtempo`, `/dssdadvice` и `/afterdl` для более точных прогнозов.\n\n"
            "📅 *История*: бот создан при участии Daniil Sergeevich и Ivan Tiron, вдохновлён идеей индекса DSID League Race Index. "
            "Исходный код и модель разработаны специально для сообщества Mutantos.\n\n"
            "🔧 *Функции*:\n"
            "• `/afterdl` — отчёт после дедлайна\n"
            "• `/aftertour` — итоги тура\n"
            "• `/dssdtempo` — таблица с темпом и LRI + прогноз\n"
            "• `/dssdadvice` — персональные рекомендации (ЛС)\n"
            "• `/fun` — игры: DoubleQuiz, GuessTheDiff, чемпионат прогнозов\n"
            "• `/halloffame` — история лиги и ЛМФК Мутанты\n"
            "• `/other` — настройки и информация (текущий раздел)\n\n"
            "📬 *Уведомления*: можно включить в настройках. Получайте оповещения, когда игрок вашей команды набирает >3 очков в реальном времени, и напоминания о дедлайне за час до начала тура."
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="other")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "other_stats":
        # Заглушка для статистики (можно добавить позже)
        text = (
            "📊 *Статистика работы*\n\n"
            "Раздел в разработке. Здесь будет отображаться:\n"
            "• Количество обработанных команд\n"
            "• Статус парсера\n"
            "• Время последнего обновления данных\n\n"
            "Следите за обновлениями!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="other")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "other":
        await other(update, context)  # возврат в главное меню other

    elif data == "back_to_main":
        from apps.dsfplbot.handlers import start
        await start(update, context)
