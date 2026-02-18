"""
Отчёт после дедлайна тура.
Собирает данные о трансферах, капитанах, чипах и формирует отчёт.
"""
import aiohttp
import logging
from collections import Counter
from typing import Dict, List, Any, Optional

from apps.dsfplbot.fpl_api import safe_request, get_bootstrap_static
from apps.dsfplbot.dssd import calculate_lri_for_manager

logger = logging.getLogger(__name__)


async def _get_entry_picks(entry_id: int, event: int, session: aiohttp.ClientSession) -> Optional[Dict]:
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{event}/picks/"
    return await safe_request(url, session)


async def _get_entry_history(entry_id: int, session: aiohttp.ClientSession) -> Optional[Dict]:
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    return await safe_request(url, session)


async def _get_league_entries(league_id: int, session: aiohttp.ClientSession) -> List[Dict]:
    """Возвращает список участников лиги с их данными."""
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    data = await safe_request(url, session)
    if not data:
        return []
    return data.get("standings", {}).get("results", [])


async def collect_afterdl_data(league_id: int, event: int) -> Dict[str, Any]:
    """Собирает данные после дедлайна для указанного тура."""
    async with aiohttp.ClientSession() as session:
        entries = await _get_league_entries(league_id, session)
        if not entries:
            return {"error": "Не удалось получить список лиги"}

        managers_data = []
        total_transfers = 0
        total_hits = 0
        chips_counter = Counter()
        captain_counter = Counter()
        transfers_in_counter = Counter()
        transfers_out_counter = Counter()

        for entry_info in entries:
            entry_id = entry_info["entry"]
            try:
                picks = await _get_entry_picks(entry_id, event, session)
                history = await _get_entry_history(entry_id, session)

                if not picks or not history:
                    logger.warning(f"No data for entry {entry_id}")
                    continue

                entry_history = next(
                    (h for h in history.get("entry_history", []) if h["event"] == event),
                    None
                )
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
                    if p.get("is_captain"):
                        captain_id = p["element"]
                        break
                if captain_id:
                    captain_counter[captain_id] += 1

                # Трансферы in/out
                if event > 1:
                    prev_picks = await _get_entry_picks(entry_id, event - 1, session)
                    if prev_picks:
                        prev_ids = {p["element"] for p in prev_picks.get("picks", [])}
                        curr_ids = {p["element"] for p in picks.get("picks", [])}
                        for pid in curr_ids - prev_ids:
                            transfers_in_counter[pid] += 1
                        for pid in prev_ids - curr_ids:
                            transfers_out_counter[pid] += 1

                lri = await calculate_lri_for_manager(entry_id, league_id)

                managers_data.append({
                    "entry_id": entry_id,
                    "team_name": entry_info.get("entry_name", "Unknown"),
                    "player_name": entry_info.get("player_name", "Unknown"),
                    "captain_id": captain_id,
                    "chip": chip,
                    "transfers": transfers,
                    "transfers_cost": transfers_cost,
                    "lri": lri,
                    "rank": entry_info.get("rank", "?"),
                    "last_rank": entry_info.get("last_rank", "?"),
                })

            except Exception as e:
                logger.error(f"Error processing entry {entry_id}: {e}")
                continue

        # Имена игроков
        bs = await get_bootstrap_static()
        elements = {e["id"]: e for e in bs.get("elements", [])} if bs else {}

        top_captains = [
            f"{elements.get(pid, {}).get('web_name', str(pid))} ({cnt})"
            for pid, cnt in captain_counter.most_common(3)
        ]
        top_in = [
            f"{elements.get(pid, {}).get('web_name', str(pid))} ({cnt})"
            for pid, cnt in transfers_in_counter.most_common(3)
        ]
        top_out = [
            f"{elements.get(pid, {}).get('web_name', str(pid))} ({cnt})"
            for pid, cnt in transfers_out_counter.most_common(3)
        ]

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
            "top_captains": ", ".join(top_captains) or "нет данных",
            "top_transfers_in": ", ".join(top_in) or "нет",
            "top_transfers_out": ", ".join(top_out) or "нет",
            "elements": elements,
        }


def format_afterdl_report(data: Dict[str, Any]) -> str:
    """Форматирует отчёт после дедлайна."""
    if "error" in data:
        return f"❌ {data['error']}"

    event = data["event"]
    lines = [
        f"📋 *Отчёт после дедлайна GW{event}*\n",
        f"👥 Участников: {data['managers_count']}",
        f"🔄 Трансферов: {data['total_transfers']} (штраф: {data['total_hits']} очков)",
        f"🃏 Чипов: {data['chips_used']}",
    ]

    cs = data["chip_stats"]
    if any(cs.values()):
        parts = []
        if cs["wildcard"]: parts.append(f"WC:{cs['wildcard']}")
        if cs["3xc"]: parts.append(f"TC:{cs['3xc']}")
        if cs["bboost"]: parts.append(f"BB:{cs['bboost']}")
        if cs["freehit"]: parts.append(f"FH:{cs['freehit']}")
        lines.append(f"   ({', '.join(parts)})")

    lines.append(f"⭐ Капитаны: {data['top_captains']}")
    lines.append(f"📈 Купленные: {data['top_transfers_in']}")
    lines.append(f"📉 Проданные: {data['top_transfers_out']}\n")

    elements = data.get("elements", {})
    lines.append("*Персональные карточки:*\n")

    for m in data["managers"]:
        captain = (elements.get(m["captain_id"], {}).get("web_name", "?")
                   if m["captain_id"] else "—")
        chip = m["chip"] if m["chip"] else "—"

        rank_str = ""
        if m.get("rank") and m.get("last_rank"):
            try:
                change = int(m["last_rank"]) - int(m["rank"])
                if change > 0:
                    rank_str = f" ▲{change}"
                elif change < 0:
                    rank_str = f" ▼{-change}"
            except (ValueError, TypeError):
                pass

        lines.append(
            f"• *{m['team_name']}* ({m['player_name']}){rank_str}\n"
            f"  Кап: {captain} | Чип: {chip} | "
            f"Трансф: {m['transfers']} (−{m['transfers_cost']}) | "
            f"LRI: {m['lri']:.1f}\n"
        )

    # Прогноз по LRI
    if data["managers"]:
        sorted_lri = sorted(data["managers"], key=lambda x: x["lri"])
        top = [m["team_name"] for m in sorted_lri[:3]]
        bot = [m["team_name"] for m in sorted_lri[-3:]]
        lines.append("\n*🔮 Прогноз (по LRI):*")
        lines.append(f"   Лучшие шансы: {', '.join(top)}")
        lines.append(f"   Аутсайдеры: {', '.join(bot)}")

    return "\n".join(lines)
