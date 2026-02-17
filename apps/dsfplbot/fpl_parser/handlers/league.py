import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def fetch_league(parser, league_id: int):
    """Обрабатывает лигу: получает данные и участников."""
    if league_id in parser.db.processed_leagues:
        return

    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    data = await parser.http_client.safe_request(url)
    if not data or "league" not in data:
        return

    league_info = data["league"]
    standings = data.get("standings", {}).get("results", [])

    season = datetime.now().strftime("%Y/%y")

    league_record = {
        "league_id": league_id,
        "name": league_info.get("name"),
        "season": season,
        "created_epoch": None,
        "entry_count": len(standings),
        "admin_entry": league_info.get("admin_entry"),
        "metadata": {"code": league_info.get("code")}
    }

    parser.db.save_league(league_record)
    parser.stats["leagues_found"] += 1

    event = data.get("standings", {}).get("event", 1)
    standings_list = []
    for entry in standings[:100]:
        manager_id = entry.get("entry")
        if not manager_id:
            continue
        standings_list.append({
            "entry_id": manager_id,
            "rank": entry.get("rank"),
            "total_points": entry.get("total"),
            "event_points": entry.get("event_total"),
            "transfers": entry.get("transfers", 0),
            "transfers_cost": entry.get("transfers_cost", 0),
        })
        if manager_id not in parser.db.processed_managers:
            parser.db.add_to_queue("manager", manager_id, priority=1)

    parser.db.save_league_standings(league_id, standings_list, event)

    logger.info(f"Лига {league_id}: {league_record['name']}, участников: {len(standings_list)}")
