import aiohttp
import asyncio
from collections import Counter
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

from apps.dsfplbot.fpl_api import safe_request, get_bootstrap_static, get_current_event, get_event_deadline
from apps.dsfplbot.dssd import calculate_lri_for_manager

logger = logging.getLogger(__name__)

_picks_cache = {}
_history_cache = {}
_standings_cache = {}

async def get_entry_picks(entry_id: int, event: int, session: aiohttp.ClientSession) -> Optional[Dict]:
    cache_key = (entry_id, event)
    if cache_key in _picks_cache:
        return _picks_cache[cache_key]
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{event}/picks/"
    data = await safe_request(url, session)
    _picks_cache[cache_key] = data
    return data

async def get_entry_history(entry_id: int, session: aiohttp.ClientSession) -> Optional[Dict]:
    if entry_id in _history_cache:
        return _history_cache[entry_id]
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    data = await safe_request(url, session)
    _history_cache[entry_id] = data
    return data

async def get_league_entries(league_id: int, session: aiohttp.ClientSession) -> List[int]:
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    data = await safe_request(url, session)
    if not data:
        return []
    standings = data.get("standings", {}).get("results", [])
    return [entry["entry"] for entry in standings]

async def get_previous_standings(league_id: int, event: int, session: aiohttp.ClientSession) -> Dict[int, int]:
    """Возвращает словарь {entry_id: rank} для предыдущего тура."""
    if event <= 1:
        return {}
    cache_key = f"{league_id}_{event-1}"
    if cache_key in _standings_cache:
        return _standings_cache[cache_key]
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/?event={event-1}"
    data = await safe_request(url, session)
    if not data:
        return {}
    standings = data.get("standings", {}).get("results", [])
    result = {entry["entry"]: entry["rank"] for entry in standings}
    _standings_cache[cache_key] = result
    return result

async def collect_afterdl_data(league_id: int, event: int) -> Dict[str, Any]:
    """Собирает данные после дедлайна для указанного тура."""
    async with aiohttp.ClientSession() as session:
        entry_ids = await get_league_entries(league_id, session)
        if not entry_ids:
            return {"error": "Не удалось получить список лиги"}

        prev_ranks = await get_previous_standings(league_id, event, session)

        managers_data = []
        total_transfers = 0
        total_hits = 0
        chips_counter = Counter()
        captain_counter = Counter()
        transfers_in_counter = Counter()
        transfers_out_counter = Counter()
        current_ranks = {}

        for entry_id in entry_ids:
            picks = await get_entry_picks(entry_id, event, session)
            history = await get_entry_history(entry_id, session)

            if not picks or not history:
                logger.warning(f"Нет данных для entry {entry_id}")
                continue

            entry_history = next((h for h in history.get("entry_history", []) if h["event"] == event), None)
            if not entry_history:
                continue

            transfers = entry_history.get("event_transfers", 0)
            transfers_cost = entry_history.get("event_transfers_cost", 0)
            total_transfers += transfers
            total_hits += transfers_cost

            chip = picks.get("active_chip")
            if chip:
                chips_counter[chip] += 1

            captain_id = None
            for p in picks.get("picks", []):
                if p["is_captain"]:
                    captain_id = p["element"]
                    break
            if captain_id:
                captain_counter[captain_id] += 1

            if event > 1:
                prev_picks = await get_entry_picks(entry_id, event-1, session)
                if prev_picks:
                    prev_ids = {p["element"] for p in prev_picks.get("picks", [])}
                    curr_ids = {p["element"] for p in picks.get("picks", [])}
                    for pid in curr_ids - prev_ids:
                        transfers_in_counter[pid] += 1
                    for pid in prev_ids - curr_ids:
                        transfers_out_counter[pid] += 1

            # Текущее место (из standings)
            standings_data = await safe_request(
                f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/", 
                session
            )
            if standings_data:
                standings = standings_data.get("standings", {}).get("results", [])
                for entry in standings:
                    if entry["entry"] == entry_id:
                        current_ranks[entry_id] = entry["rank"]
                        break

            managers_data.append({
                "entry_id": entry_id,
                "team_name": history.get("name", "Unknown"),
                "player_name": f"{history.get('player_first_name', '')} {history.get('player_last_name', '')}".strip(),
                "captain_id": captain_id,
                "chip": chip,
                "transfers": transfers,
                "transfers_cost": transfers_cost,
                "lri": await calculate_lri_for_manager(entry_id, league_id),
                "prev_rank": prev_ranks.get(entry_id),
                "current_rank": current_ranks.get(entry_id),
            })

        # Вычисляем изменения мест
        for m in managers_data:
            if m["prev_rank"] and m["current_rank"]:
                m["rank_change"] = m["prev_rank"] - m["current_rank"]
            else:
                m["rank_change"] = None

        # Получаем данные игроков для отображения имён
        bs = await get_bootstrap_static()
        elements = {e["id"]: e for e in bs["elements"]}

        top_captains = []
        for pid, cnt in captain_counter.most_common(3):
            name = elements.get(pid, {}).get("web_name", str(pid))
            top_captains.append(f"{name} ({cnt})")

        top_in = []
        for pid, cnt in transfers_in_counter.most_common(3):
            name = elements.get(pid, {}).get("web_name", str(pid))
            top_in.append(f"{name} ({cnt})")
        top_out = []
        for pid, cnt in transfers_out_counter.most_common(3):
            name = elements.get(pid, {}).get("web_name", str(pid))
            top_out.append(f"{name} ({cnt})")

        chip_stats = {
            "wildcard": chips_counter.get("wildcard", 0),
            "3xc": chips_counter.get("3xc", 0),
            "bboost": chips_counter.get("bboost", 0),
            "freehit": chips_counter.get("freehit", 0),
        }

        return {
            "event": event,
            "managers_count": len(managers_data),
            "managers": managers_data,
            "total_transfers": total_transfers,
            "total_hits": total_hits,
            "chips_used": sum(chip_stats.values()),
            "chip_stats": chip_stats,
            "top_captains": ", ".join(top_captains) if top_captains else "нет данных",
            "top_transfers_in": ", ".join(top_in) if top_in else "нет",
            "top_transfers_out": ", ".join(top_out) if top_out else "нет",
            "elements": elements,
        }

def format_afterdl_report(data: Dict[str, Any]) -> str:
    if "error" in data:
        return f"❌ {data['error']}"

    event = data["event"]
    lines = [
        f"📋 *Отчёт после дедлайна тура {event}*\n",
        f"👥 *Участников:* {data['managers_count']}",
        f"🔄 *Трансферов:* {data['total_transfers']} (штраф: {data['total_hits']} очков)",
        f"🃏 *Использовано чипов:* {data['chips_used']}",
        f"   • Wildcard: {data['chip_stats']['wildcard']}",
        f"   • Triple Captain: {data['chip_stats']['3xc']}",
        f"   • Bench Boost: {data['chip_stats']['bboost']}",
        f"   • Free Hit: {data['chip_stats']['freehit']}",
        f"⭐ *Популярные капитаны:* {data['top_captains']}",
        f"📈 *Топ-3 купленных:* {data['top_transfers_in']}",
        f"📉 *Топ-3 проданных:* {data['top_transfers_out']}\n",
        "*📌 Персональные карточки:*\n"
    ]

    elements = data.get("elements", {})
    for m in data["managers"]:
        captain = elements.get(m["captain_id"], {}).get("web_name", str(m["captain_id"])) if m["captain_id"] else "—"
        chip = m["chip"] if m["chip"] else "—"
        change_str = ""
        if m["rank_change"] is not None:
            if m["rank_change"] > 0:
                change_str = f"▲{m['rank_change']}"
            elif m["rank_change"] < 0:
                change_str = f"▼{-m['rank_change']}"
            else:
                change_str = "•"
        rank_info = f" (место: {m['current_rank']} {change_str})" if m["current_rank"] else ""
        lines.append(
            f"• *{m['team_name']}* ({m['player_name']}){rank_info}\n"
            f"  Капитан: {captain} | Чип: {chip} | Трансферы: {m['transfers']} (штраф {m['transfers_cost']}) | LRI: {m['lri']:.2f}\n"
        )

    if data["managers"]:
        sorted_by_lri = sorted(data["managers"], key=lambda x: x["lri"])
        top_lri = sorted_by_lri[:3]
        bottom_lri = sorted_by_lri[-3:]
        lines.append("\n*🔮 Прогноз на тур (по LRI):*")
        lines.append(f"   Лучшие шансы: {', '.join([m['team_name'] for m in top_lri])}")
        lines.append(f"   Аутсайдеры: {', '.join([m['team_name'] for m in bottom_lri])}")

    return "\n".join(lines)
