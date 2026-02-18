"""
Итоги завершённого тура.
Собирает очки менеджеров, лучших игроков, статистику тура.
"""
import asyncio
import logging
from collections import Counter
from typing import Dict, List, Any

from apps.dsfplbot.fpl_api import (
    get_bootstrap_static, get_entry_history,
    get_entry_picks, get_league_standings, get_event_live
)

logger = logging.getLogger(__name__)


async def collect_aftertour_data(league_id: int, event: int) -> Dict[str, Any]:
    """Собирает данные для отчёта по завершённому туру."""
    standings_data = await get_league_standings(league_id)
    if not standings_data:
        return {"error": "Не удалось получить список лиги"}

    results = standings_data.get("standings", {}).get("results", [])
    if not results:
        return {"error": "Нет участников в лиге"}

    entries = [r["entry"] for r in results]
    entry_names = {r["entry"]: r.get("entry_name", "Unknown") for r in results}
    player_names = {r["entry"]: r.get("player_name", "Unknown") for r in results}

    # Live-очки игроков
    live_data = await get_event_live(event)
    elements_live = {}
    if live_data:
        for elem in live_data.get("elements", []):
            elements_live[elem["id"]] = elem["stats"]["total_points"]

    # Параллельно собираем данные
    history_tasks = [get_entry_history(eid) for eid in entries]
    picks_tasks = [get_entry_picks(eid, event) for eid in entries]

    history_results = await asyncio.gather(*history_tasks, return_exceptions=True)
    picks_results = await asyncio.gather(*picks_tasks, return_exceptions=True)

    managers = []
    total_transfers = 0
    total_hits = 0
    chip_counter = Counter()
    captain_counter = Counter()
    player_points = Counter()

    for i, entry_id in enumerate(entries):
        history = history_results[i] if not isinstance(history_results[i], Exception) else None
        picks = picks_results[i] if not isinstance(picks_results[i], Exception) else None

        if not history or not picks:
            continue

        current = next(
            (h for h in history.get("entry_history", []) if h["event"] == event),
            None
        )
        if not current:
            continue

        previous = next(
            (h for h in history.get("entry_history", []) if h["event"] == event - 1),
            None
        )

        points = current.get("points", 0)
        transfers = current.get("event_transfers", 0)
        transfers_cost = current.get("event_transfers_cost", 0)
        total_transfers += transfers
        total_hits += transfers_cost

        chip = picks.get("active_chip")
        if chip:
            chip_counter[chip] += 1

        captain_id = None
        for p in picks.get("picks", []):
            if p.get("is_captain"):
                captain_id = p["element"]
                break
        if captain_id:
            captain_counter[captain_id] += 1

        # Суммируем очки игроков
        if elements_live:
            for p in picks.get("picks", []):
                pid = p["element"]
                player_points[pid] += elements_live.get(pid, 0)

        managers.append({
            "entry_id": entry_id,
            "team_name": entry_names.get(entry_id, "Unknown"),
            "player_name": player_names.get(entry_id, "Unknown"),
            "points": points,
            "transfers": transfers,
            "transfers_cost": transfers_cost,
            "chip": chip,
            "captain_id": captain_id,
            "previous_total": previous["total_points"] if previous else current["total_points"] - points,
            "current_total": current["total_points"],
        })

    # Изменение мест
    current_sorted = sorted(managers, key=lambda x: -x["current_total"])
    current_ranks = {m["entry_id"]: i + 1 for i, m in enumerate(current_sorted)}
    prev_sorted = sorted(managers, key=lambda x: -x["previous_total"])
    prev_ranks = {m["entry_id"]: i + 1 for i, m in enumerate(prev_sorted)}

    for m in managers:
        m["rank_change"] = prev_ranks.get(m["entry_id"], 0) - current_ranks.get(m["entry_id"], 0)

    top_managers = sorted(managers, key=lambda x: -x["points"])[:5]

    # Имена игроков
    bs = await get_bootstrap_static()
    elements = {e["id"]: e for e in bs.get("elements", [])} if bs else {}

    top_players = [
        f"{elements.get(pid, {}).get('web_name', str(pid))} ({pts} pts)"
        for pid, pts in player_points.most_common(5)
    ]

    top_captains = [
        f"{elements.get(pid, {}).get('web_name', str(pid))} ({cnt})"
        for pid, cnt in captain_counter.most_common(5)
    ]

    chip_breakdown = {
        "wildcard": chip_counter.get("wildcard", 0),
        "3xc": chip_counter.get("3xc", 0),
        "bboost": chip_counter.get("bboost", 0),
        "freehit": chip_counter.get("freehit", 0),
    }

    return {
        "event": event,
        "managers": managers,
        "top_managers": top_managers,
        "total_transfers": total_transfers,
        "total_hits": total_hits,
        "chip_breakdown": chip_breakdown,
        "top_players": top_players,
        "top_captains": top_captains,
    }


def format_aftertour_report(data: Dict[str, Any]) -> str:
    """Форматирует отчёт по туру."""
    if "error" in data:
        return f"❌ {data['error']}"

    event = data["event"]
    lines = [
        f"📊 *Итоги GW{event}*\n",
        f"👥 Менеджеров: {len(data['managers'])}",
        f"🔄 Трансферов: {data['total_transfers']} (штраф: {data['total_hits']})",
    ]

    cb = data["chip_breakdown"]
    chips_total = sum(cb.values())
    if chips_total:
        parts = []
        if cb["wildcard"]: parts.append(f"WC:{cb['wildcard']}")
        if cb["3xc"]: parts.append(f"TC:{cb['3xc']}")
        if cb["bboost"]: parts.append(f"BB:{cb['bboost']}")
        if cb["freehit"]: parts.append(f"FH:{cb['freehit']}")
        lines.append(f"🃏 Чипы: {', '.join(parts)}")

    lines.append("\n*📈 Таблица:*\n")

    managers_sorted = sorted(data["managers"], key=lambda x: -x["current_total"])
    for idx, m in enumerate(managers_sorted, 1):
        change = m["rank_change"]
        arrow = "▲" if change > 0 else "▼" if change < 0 else "•"
        change_text = f"{arrow}{abs(change)}" if change != 0 else "•"
        lines.append(
            f"{idx}. *{m['team_name']}* — {m['current_total']} pts "
            f"({m['points']} в туре) {change_text}"
        )

    lines.append("\n*🔥 Лучшие менеджеры тура:*")
    for i, m in enumerate(data["top_managers"], 1):
        chip_info = f", чип: {m['chip']}" if m["chip"] else ""
        lines.append(f"{i}. {m['team_name']} — {m['points']} pts{chip_info}")

    if data["top_players"]:
        lines.append("\n*⚽ Топ игроков (в составах лиги):*")
        for player in data["top_players"]:
            lines.append(f"• {player}")

    if data["top_captains"]:
        lines.append("\n*👑 Капитаны:*")
        for cap in data["top_captains"]:
            lines.append(f"• {cap}")

    return "\n".join(lines)
