import aiohttp
import logging
from typing import List, Dict, Optional
from collections import defaultdict

from apps.dsfplbot.fpl_api import get_entry_picks, get_entry_history, get_bootstrap_static
from apps.dsfplbot.database import get_user_fpl_id
from apps.dsfplbot.fpl_data_reader import get_manager_history

logger = logging.getLogger(__name__)

async def predict_player_points(player_id: int, start_event: int, weeks: int = 3) -> float:
    """
    Прогноз очков игрока на ближайшие weeks туров.
    Учитывает:
    - среднюю форму за последние 5 матчей
    - ожидаемые голы/передачи (xG/xA) из последних матчей (если есть в БД)
    - сложность ближайших матчей (TODO)
    """
    # Пока простая заглушка: среднее за последние 5 матчей из истории
    history = await get_manager_history(player_id)  # это история менеджера, не игрока. Нужно переделать!
    # В реальности нужна история игрока, а не менеджера. Пока оставим заглушку.
    return 4.5

async def get_player_details(player_id: int):
    """Получает детальную информацию об игроке из bootstrap-static."""
    bs = await get_bootstrap_static()
    elements = {e["id"]: e for e in bs["elements"]}
    return elements.get(player_id)

async def generate_advice(telegram_id: int, league_id: int, event: int) -> str:
    """Генерирует персональные рекомендации по трансферам."""
    fpl_id = await get_user_fpl_id(telegram_id)
    if not fpl_id:
        return "🔐 Сначала привяжите FPL ID через /link."

    # Получаем текущий состав и историю менеджера
    picks = await get_entry_picks(fpl_id, event)
    history = await get_entry_history(fpl_id)
    if not picks or not history:
        return "❌ Не удалось получить данные вашей команды."

    # Получаем бюджет и количество свободных трансферов
    entry_history = next((h for h in history.get("entry_history", []) if h["event"] == event), {})
    bank = entry_history.get("bank", 0) / 10  # в FPL банк хранится в десятых
    # Количество свободных трансферов (обычно 1, но можно вычислить из истории)
    free_transfers = 1
    if event > 1:
        prev = next((h for h in history.get("entry_history", []) if h["event"] == event-1), None)
        if prev:
            # Если в прошлом туре не было трансферов, можно накопить
            free_transfers = 1 + max(0, (prev.get("event_transfers", 0) - prev.get("event_transfers_cost", 0) // 4))
    # упрощённо: оставим 1

    # Состав
    picks_list = picks.get("picks", [])
    bs = await get_bootstrap_static()
    elements = {e["id"]: e for e in bs["elements"]}

    team = []
    for p in picks_list:
        player = elements.get(p["element"])
        if player:
            team.append({
                "id": player["id"],
                "web_name": player["web_name"],
                "element_type": player["element_type"],
                "now_cost": player["now_cost"] / 10,
                "form": float(player.get("form", 0)),
                "selected_by": float(player.get("selected_by_percent", 0)),
                "points_per_game": float(player.get("points_per_game", 0)),
                "minutes": player.get("minutes", 0),
                "goals_scored": player.get("goals_scored", 0),
                "assists": player.get("assists", 0),
                "clean_sheets": player.get("clean_sheets", 0),
                "bonus": player.get("bonus", 0),
            })

    # Определяем слабые позиции: игроки с низкой формой и низкими PPG
    # Также учитываем, если игрок мало играет (minutes < 60 в среднем)
    weak = []
    for p in team:
        reasons = []
        if p["form"] < 3.0:
            reasons.append(f"форма {p['form']:.1f} (низкая)")
        if p["points_per_game"] < 3.0:
            reasons.append(f"PPG {p['points_per_game']:.1f} (низкий)")
        if p["minutes"] < 60 and p["minutes"] > 0:  # если играет, но мало
            reasons.append("мало игрового времени")
        if reasons:
            weak.append((p, reasons))

    if not weak:
        return "✅ Ваш состав выглядит сбалансированно! Нет явных слабых мест."

    # Сортируем слабых по убыванию цены (чтобы было куда улучшать)
    weak.sort(key=lambda x: -x[0]["now_cost"])

    recommendations = []
    for w, reasons in weak[:5]:  # берём до 5 слабых, но потом выберем лучшие 3
        # Ищем замену: из той же позиции, с лучшей формой, ценой <= bank + w["now_cost"]
        candidates = []
        for player in elements.values():
            # Проверяем позицию
            if player["element_type"] != w["element_type"]:
                continue
            # Исключаем уже имеющихся игроков
            if player["id"] in [p["id"] for p in team]:
                continue
            # Проверяем бюджет
            if player["now_cost"] / 10 > bank + w["now_cost"]:
                continue
            # Критерий: форма > 5.0 или points_per_game > 5.0
            if float(player.get("form", 0)) > 5.0 or float(player.get("points_per_game", 0)) > 5.0:
                candidates.append(player)

        if candidates:
            # Выбираем лучшего по сумме form + points_per_game
            best = max(candidates, key=lambda x: float(x.get("form", 0)) + float(x.get("points_per_game", 0)))
            gain = (float(best.get("form", 0)) + float(best.get("points_per_game", 0))) - (w["form"] + w["points_per_game"])
            recommendations.append({
                "out": w["web_name"],
                "in": best["web_name"],
                "cost": best["now_cost"] / 10,
                "gain": round(gain, 1),
                "reasons": ", ".join(reasons)
            })

    if not recommendations:
        return "🤷‍♂️ Не найдено подходящих замен в рамках бюджета."

    # Выбираем топ-3 по приросту
    recommendations.sort(key=lambda x: -x["gain"])
    top3 = recommendations[:3]

    text = "📋 *Персональные рекомендации*\n\n"
    for r in top3:
        text += f"• Замените *{r['out']}* на *{r['in']}* (💰 {r['cost']} млн, 📈 +{r['gain']} очков формы/PPG)\n"
        text += f"  *Почему:* {r['reasons']}\n\n"
    text += "\n*Важно:* прогноз основан на текущей форме и PPG. Полная модель DSSD в разработке."
    return text
