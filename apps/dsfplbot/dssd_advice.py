"""
Персональные советы по трансферам.
Анализирует текущий состав менеджера и предлагает замены
на основе формы, PPG и бюджета.
"""
import logging
from typing import Optional

from apps.dsfplbot.fpl_api import get_entry_picks, get_entry_history, get_bootstrap_static
from apps.dsfplbot.database import get_user_fpl_id

logger = logging.getLogger(__name__)


async def generate_advice(telegram_id: int, league_id: int, event: int) -> str:
    """Генерирует персональные рекомендации по трансферам."""
    fpl_id = await get_user_fpl_id(telegram_id)
    if not fpl_id:
        return "🔐 Сначала привяжите FPL ID через /link."

    if not event:
        return "❌ Не удалось определить текущий тур."

    try:
        picks = await get_entry_picks(fpl_id, event)
        history = await get_entry_history(fpl_id)
    except Exception as e:
        logger.error(f"Error fetching data for {fpl_id}: {e}")
        return "❌ Не удалось получить данные вашей команды."

    if not picks or not history:
        return "❌ Не удалось получить данные вашей команды. Проверьте FPL ID."

    # Получаем бюджет
    entry_history = next(
        (h for h in history.get("entry_history", []) if h["event"] == event),
        {}
    )
    bank = entry_history.get("bank", 0) / 10  # в FPL банк в десятых

    # Получаем состав
    picks_list = picks.get("picks", [])
    try:
        bs = await get_bootstrap_static()
    except Exception as e:
        logger.error(f"Error fetching bootstrap: {e}")
        return "❌ Не удалось получить данные игроков."

    if not bs:
        return "❌ Не удалось получить данные FPL."

    elements = {e["id"]: e for e in bs["elements"]}

    team = []
    team_ids = set()
    for p in picks_list:
        player = elements.get(p["element"])
        if player:
            team.append({
                "id": player["id"],
                "web_name": player["web_name"],
                "element_type": player["element_type"],
                "now_cost": player["now_cost"] / 10,
                "form": float(player.get("form", 0)),
                "ppg": float(player.get("points_per_game", 0)),
                "minutes": player.get("minutes", 0),
            })
            team_ids.add(player["id"])

    # Определяем слабые позиции
    weak = []
    for p in team:
        reasons = []
        if p["form"] < 3.0:
            reasons.append(f"форма {p['form']:.1f}")
        if p["ppg"] < 3.0:
            reasons.append(f"PPG {p['ppg']:.1f}")
        if 0 < p["minutes"] < 60:
            reasons.append("мало минут")
        if reasons:
            weak.append((p, reasons))

    if not weak:
        return "✅ Ваш состав выглядит сбалансированно! Нет явных слабых мест."

    weak.sort(key=lambda x: -x[0]["now_cost"])

    # Ищем замены
    recommendations = []
    for w, reasons in weak[:5]:
        candidates = []
        for player in elements.values():
            if player["element_type"] != w["element_type"]:
                continue
            if player["id"] in team_ids:
                continue
            if player["now_cost"] / 10 > bank + w["now_cost"]:
                continue
            p_form = float(player.get("form", 0))
            p_ppg = float(player.get("points_per_game", 0))
            if p_form > 5.0 or p_ppg > 5.0:
                candidates.append(player)

        if candidates:
            best = max(candidates, key=lambda x: float(x.get("form", 0)) + float(x.get("points_per_game", 0)))
            gain = (float(best.get("form", 0)) + float(best.get("points_per_game", 0))) - (w["form"] + w["ppg"])
            recommendations.append({
                "out": w["web_name"],
                "in": best["web_name"],
                "cost": best["now_cost"] / 10,
                "gain": round(gain, 1),
                "reasons": ", ".join(reasons)
            })

    if not recommendations:
        return "🤷 Не найдено подходящих замен в рамках бюджета."

    recommendations.sort(key=lambda x: -x["gain"])
    top3 = recommendations[:3]

    text = "📋 *Персональные рекомендации*\n\n"
    for r in top3:
        text += (
            f"• Замените *{r['out']}* на *{r['in']}* "
            f"(💰 {r['cost']:.1f} млн, 📈 +{r['gain']})\n"
            f"  _Причина: {r['reasons']}_\n\n"
        )
    text += "_Прогноз на основе формы и PPG. Полная модель DSSD в разработке._"
    return text
