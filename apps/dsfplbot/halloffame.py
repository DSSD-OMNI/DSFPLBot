import csv
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.dsfplbot.database import get_api_season, get_legacy_season

logger = logging.getLogger(__name__)

async def get_all_seasons():
    """Возвращает список всех сезонов из CSV."""
    seasons = set()
    csv_path = "apps/dsfplbot/FPL League History.csv"
    if not os.path.exists(csv_path):
        logger.warning("FPL League History.csv not found")
        return ["2023/24", "2022/23", "2021/22"]  # fallback
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seasons.add(row["Season"])
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return ["2023/24", "2022/23", "2021/22"]
    return sorted(list(seasons), reverse=True)

async def halloffame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seasons = await get_all_seasons()
    if not seasons:
        seasons = ["2023/24", "2022/23", "2021/22"]
    # Разбиваем на ряды по 2 сезона для компактности
    keyboard = []
    for i in range(0, len(seasons), 2):
        row = []
        row.append(InlineKeyboardButton(seasons[i], callback_data=f"hof_{seasons[i]}"))
        if i+1 < len(seasons):
            row.append(InlineKeyboardButton(seasons[i+1], callback_data=f"hof_{seasons[i+1]}"))
        keyboard.append(row)
    # Добавляем кнопку для ЛМФК Мутанты
    keyboard.append([InlineKeyboardButton("⚽ ЛМФК Мутанты", callback_data="hof_mutants")])
    await update.message.reply_text(
        "🏆 *Зал славы FPL*\nВыберите сезон или перейдите в раздел Мутантов:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def hof_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "hof_mutants":
        # Заглушка для ЛМФК Мутанты
        text = (
            "⚽ *ЛМФК Мутанты*\n\n"
            "Раздел в разработке. Здесь будет история выступлений мини-футбольной команды.\n\n"
            "Планируется:\n"
            "• Результаты матчей по сезонам\n"
            "• Статистика игроков (голы, ассисты, карточки)\n"
            "• Привязка к профилям Telegram\n"
            "• Фото и видео моменты\n\n"
            "Следите за обновлениями!"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
        return

    season = data.replace("hof_", "")
    api_data = await get_api_season(season)
    legacy_data = await get_legacy_season(season)

    merged = []
    # Данные из API (проверенные)
    for i, a in enumerate(api_data):
        merged.append({
            "pos": i+1,
            "manager": a["team_name"],
            "team": a["team_name"],
            "points": a["total_points"],
            "rank": a["rank"],
            "verified": True
        })
    # Данные из CSV
    for l in legacy_data:
        merged.append({
            "pos": l["pos"],
            "manager": l["manager"],
            "team": l["team"],
            "points": l["total_points"],
            "rank": l["overall_rank"],
            "verified": bool(l["verified"])
        })
    merged.sort(key=lambda x: x["pos"])

    lines = [f"🏆 Зал славы FPL – сезон {season}\n"]
    for e in merged:
        mark = "✅" if e["verified"] else "⚠️"
        lines.append(f"{e['pos']}. *{e['manager']}* – {e['team']} – {e['points']} pts (OR: {e['rank']}) {mark}")
    if any(not e["verified"] for e in merged):
        lines.append("\n⚠️ – данные из CSV, требуют проверки. ✅ – официальные данные FPL API.")
    # Кнопка назад
    keyboard = [[InlineKeyboardButton("🔙 Назад к сезонам", callback_data="back_to_hof")]]
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_hof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await halloffame(update, context)
