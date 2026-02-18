"""
Зал славы — история лиги по сезонам из CSV и FPL API.
"""
import csv
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from apps.dsfplbot.database import get_api_season, get_legacy_season

logger = logging.getLogger(__name__)


async def _get_all_seasons() -> list:
    """Возвращает список всех сезонов из CSV."""
    csv_path = os.path.join(os.path.dirname(__file__), "FPL League History.csv")
    seasons = set()
    try:
        if not os.path.exists(csv_path):
            logger.warning("FPL League History.csv not found")
            return ["2023/24", "2022/23", "2021/22"]
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seasons.add(row["Season"])
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return ["2023/24", "2022/23", "2021/22"]
    return sorted(list(seasons), reverse=True)


async def halloffame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора сезонов."""
    seasons = await _get_all_seasons()
    if not seasons:
        seasons = ["2023/24", "2022/23", "2021/22"]

    keyboard = []
    for i in range(0, len(seasons), 2):
        row = [InlineKeyboardButton(seasons[i], callback_data=f"hof_{seasons[i]}")]
        if i + 1 < len(seasons):
            row.append(InlineKeyboardButton(seasons[i + 1], callback_data=f"hof_{seasons[i+1]}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⚽ ЛМФК Мутанты", callback_data="hof_mutants")])

    text = "🏆 *Зал славы FPL*\nВыберите сезон:"

    if update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def hof_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-кнопок зала славы."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_hof":
        await halloffame(update, context)
        return

    if data == "hof_mutants":
        text = (
            "⚽ *ЛМФК Мутанты*\n\n"
            "Раздел в разработке.\n\n"
            "Планируется:\n"
            "• Результаты матчей по сезонам\n"
            "• Статистика игроков\n"
            "• Фото и видео моменты\n\n"
            "Следите за обновлениями!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад к сезонам", callback_data="back_to_hof")]]
        await query.edit_message_text(text, parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Конкретный сезон
    season = data.replace("hof_", "")

    try:
        api_data = await get_api_season(season)
        legacy_data = await get_legacy_season(season)

        merged = []
        # API-данные (проверенные)
        for i, a in enumerate(api_data):
            merged.append({
                "pos": i + 1, "manager": a["team_name"], "team": a["team_name"],
                "points": a["total_points"], "rank": a["rank"], "verified": True
            })

        # CSV-данные (если API пусто)
        if not merged:
            for l in legacy_data:
                merged.append({
                    "pos": l["pos"], "manager": l["manager"], "team": l["team"],
                    "points": l["total_points"], "rank": l["overall_rank"],
                    "verified": bool(l["verified"])
                })

        merged.sort(key=lambda x: int(x["pos"]))

        if not merged:
            text = f"🏆 *Сезон {season}* — нет данных."
        else:
            lines = [f"🏆 *Зал славы — {season}*\n"]
            for e in merged:
                mark = "✅" if e["verified"] else "⚠️"
                lines.append(
                    f"{e['pos']}. *{e['manager']}* — {e['team']} — "
                    f"{e['points']} pts (OR: {e['rank']}) {mark}"
                )
            if any(not e["verified"] for e in merged):
                lines.append("\n⚠️ — данные из CSV  ✅ — данные FPL API")
            text = "\n".join(lines)

        keyboard = [[InlineKeyboardButton("🔙 Назад к сезонам", callback_data="back_to_hof")]]
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in hof_callback for {season}: {e}")
        await query.edit_message_text(f"❌ Ошибка при загрузке сезона {season}.")
