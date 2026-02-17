import asyncio
from collections import Counter
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

from apps.dsfplbot.fpl_api import (
    safe_request, get_bootstrap_static, get_entry_history, 
    get_entry_picks, get_league_standings, get_event_live,
    get_current_event, is_event_finished
)
from apps.dsfplbot.dssd import calculate_lri_for_manager

logger = logging.getLogger(__name__)

async def collect_aftertour_data(league_id: int, event: int) -> Dict[str, Any]:
    """Собирает данные для отчёта по завершённому туру."""
    standings_data = await get_league_standings(league_id)
    if not standings_data:
        return {"error": "Не удалось получить список лиги"}
    
    entries = [r["entry"] for r in standings_data.get("standings", {}).get("results", [])]
    if not entries:
        return {"error": "Нет участников в лиге"}

    # Получаем live-очки игроков в этом туре
    live_data = await get_event_live(event)
    elements_live = {}
    if live_data:
        for elem in live_data.get("elements", []):
            elements_live[elem["id"]] = elem["stats"]["total_points"]

    # Собираем данные по менеджерам параллельно
    tasks = []
    for entry_id in entries:
        tasks.append(get_entry_history(entry_id))
        tasks.append(get_entry_picks(entry_id, event))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    history_list = results[:len(entries)]
    picks_list = results[len(entries):]

    managers = []
    total_transfers = 0
    total_hits = 0
    chip_counter = Counter()
    captain_counter = Counter()
    player_points = Counter()  # очки игроков в составах

    for i, entry_id in enumerate(entries):
        history = history_list[i] if not isinstance(history_list[i], Exception) else None
        picks = picks_list[i] if not isinstance(picks_list[i], Exception) else None
        
        if not history or not picks:
            logger.warning(f"Неполные данные для entry {entry_id}")
            continue

        current = next((h for h in history.get("entry_history", []) if h["event"] == event), None)
        previous = next((h for h in history.get("entry_history", []) if h["event"] == event-1), None)
        
        if not current:
            continue

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
            if p["is_captain"]:
                captain_id = p["element"]
                break
        if captain_id:
            captain_counter[captain_id] += 1

        # Суммируем очки игроков для рейтинга
        if elements_live:
            for p in picks.get("picks", []):
                player_id = p["element"]
                player_points[player_id] += elements_live.get(player_id, 0)

        managers.append({
            "entry_id": entry_id,
            "team_name": history.get("name", "Unknown"),
            "player_name": f"{history.get('player_first_name', '')} {history.get('player_last_name', '')}".strip(),
            "points": points,
            "transfers": transfers,
            "transfers_cost": transfers_cost,
            "chip": chip,
            "captain_id": captain_id,
            "previous_total": previous["total_points"] if previous else current["total_points"] - points,
            "current_total": current["total_points"],
        })

    # Вычисляем изменение мест
    current_sorted = sorted(managers, key=lambda x: -x["current_total"])
    current_ranks = {m["entry_id"]: i+1 for i, m in enumerate(current_sorted)}
    prev_sorted = sorted(managers, key=lambda x: -x["previous_total"])
    prev_ranks = {m["entry_id"]: i+1 for i, m in enumerate(prev_sorted)}
    
    for m in managers:
        m["rank_change"] = prev_ranks.get(m["entry_id"], 0) - current_ranks.get(m["entry_id"], 0)

    # Топ-5 менеджеров тура
    top_managers = sorted(managers, key=lambda x: -x["points"])[:5]

    # Получаем данные игроков для имён
    bs = await get_bootstrap_static()
    elements = {e["id"]: e for e in bs["elements"]}

    # Топ-5 игроков тура (по очкам в составах)
    top_players = []
    for pid, pts in player_points.most_common(5):
        name = elements.get(pid, {}).get("web_name", str(pid))
        top_players.append(f"{name} ({pts} pts)")

    # Топ-5 капитанов
    top_captains = []
    for pid, cnt in captain_counter.most_common(5):
        name = elements.get(pid, {}).get("web_name", str(pid))
        top_captains.append(f"{name} ({cnt})")

    # Статистика чипов
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
        f"📊 *Итоги тура {event}*\n",
        f"👥 *Всего менеджеров:* {len(data['managers'])}",
        f"🔄 *Трансферы:* {data['total_transfers']} (штраф: {data['total_hits']})",
        f"🃏 *Использовано чипов:* {sum(data['chip_breakdown'].values())}",
        f"   • Wildcard: {data['chip_breakdown']['wildcard']}",
        f"   • Triple Captain: {data['chip_breakdown']['3xc']}",
        f"   • Bench Boost: {data['chip_breakdown']['bboost']}",
        f"   • Free Hit: {data['chip_breakdown']['freehit']}\n",
        "*📈 Таблица изменений:*\n"
    ]

    managers_sorted = sorted(data["managers"], key=lambda x: -x["current_total"])
    for idx, m in enumerate(managers_sorted, 1):
        change = m["rank_change"]
        arrow = "▲" if change > 0 else "▼" if change < 0 else "•"
        change_text = f"{arrow}{abs(change) if change != 0 else ''}"
        lines.append(
            f"{idx}. *{m['team_name']}* – {m['current_total']} pts "
            f"({m['points']} в туре) {change_text}"
        )

    lines.append("\n*🔥 Лучшие менеджеры тура:*")
    for i, m in enumerate(data["top_managers"], 1):
        chip_info = f", чип: {m['chip']}" if m['chip'] else ""
        lines.append(f"{i}. {m['team_name']} – {m['points']} pts{chip_info}")

    lines.append("\n*⚽ Топ-5 игроков тура (в составах лиги):*")
    for player in data["top_players"]:
        lines.append(f"• {player}")

    lines.append("\n*👑 Самые популярные капитаны:*")
    for cap in data["top_captains"]:
        lines.append(f"• {cap}")

    return "\n".join(lines)
