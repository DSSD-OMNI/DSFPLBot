"""
Модуль DSSD — расчёт LRI и генерация советов.
LRI (League Race Index) рассчитывается парсером и хранится в таблицах lri_scores и features.
Этот модуль читает готовые значения и генерирует персональные советы.
"""
import logging
from typing import List, Dict, Any, Optional

from apps.dsfplbot.fpl_data_reader import (
    get_latest_lri_for_entry, get_form_for_entry, get_features
)

logger = logging.getLogger(__name__)

# 21 фактор модели DSSD (для справки — полная модель пока не реализована)
WEIGHTS = {
    'xG': 0.13, 'xA': 0.08, 'form_last_5': 0.07, 'minutes_last_5': 0.07,
    'ict_index': 0.05, 'bonus_points_avg': 0.05, 'selected_by_percent': 0.04,
    'opponent_elo': 0.08, 'home_advantage': 0.05, 'fixture_difficulty': 0.04,
    'team_xG_trend': 0.05, 'opponent_xG_conceded': 0.04,
    'days_since_last_match': 0.03, 'international_break_flag': 0.02,
    'transfers_in_round': 0.04, 'volatility': 0.03, 'form_trend': 0.04,
    'captain_diversity': 0.03, 'chips_used': 0.04, 'cbit': 0.02,
    'non_penalty_xG': 0.03,
}


async def calculate_lri_for_manager(entry_id: int, league_id: int) -> float:
    """
    Возвращает LRI менеджера из БД парсера.
    Если данных нет — возвращает 5.0 (нейтральное значение).
    """
    lri = await get_latest_lri_for_entry(entry_id)
    return lri if lri is not None else 5.0


def generate_personalized_advice(standings: List[Dict], weeks: int) -> str:
    """
    Генерирует текстовые советы для каждого менеджера на основе таблицы.
    standings: список dict с ключами manager_name, form, lri и др.
    """
    if not standings:
        return "Нет данных для анализа."

    # Вычисляем средние показатели лиги
    form_values = [s.get("form", 0) for s in standings if s.get("form")]
    lri_values = [s.get("lri", 5.0) for s in standings]
    avg_form = sum(form_values) / len(form_values) if form_values else 0
    avg_lri = sum(lri_values) / len(lri_values) if lri_values else 5.0

    advice_lines = []
    for s in standings:
        name = s.get("player_name", s.get("manager_name", "Unknown"))
        adv = []

        form = s.get("form", 0)
        lri = s.get("lri", 5.0)

        if form and form < avg_form - 2:
            adv.append("📉 Темп ниже среднего — стоит усилить состав.")
        elif form and form > avg_form + 2:
            adv.append("📈 Отличная форма! Держите темп.")

        if lri < avg_lri - 1.5:
            adv.append("⚠️ LRI значительно ниже среднего — шансы на лидерство падают.")
        elif lri > avg_lri + 1.5:
            adv.append("🌟 LRI выше среднего — вы в числе фаворитов!")

        games = s.get("games_played", weeks)
        if games < weeks:
            adv.append(f"⚠️ Данные только за {games} тур(ов) из {weeks}.")

        if adv:
            advice_lines.append(f"• *{name}*: " + " ".join(adv))

    return "\n".join(advice_lines) if advice_lines else "✨ У всех менеджеров стабильные показатели!"
