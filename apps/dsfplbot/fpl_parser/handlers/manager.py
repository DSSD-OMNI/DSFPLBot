import logging

logger = logging.getLogger(__name__)


async def fetch_manager(parser, manager_id: int):
    """Обрабатывает менеджера: получает профиль и историю."""
    if manager_id in parser.db.processed_managers:
        return

    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/"
    data = await parser.http_client.safe_request(url)
    if not data:
        return

    first = data.get('player_first_name', '')
    last = data.get('player_last_name', '')
    player_name = f"{first} {last}".strip()
    team_name = data.get('name', 'Unknown')
    region = data.get('player_region_name', None)
    overall_rank = None

    manager_record = {
        "manager_id": manager_id,
        "player_name": player_name,
        "team_name": team_name,
        "region": region,
        "overall_rank": overall_rank,
    }
    parser.db.save_manager(manager_record)
    parser.stats["managers_found"] += 1

    history_url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
    history_data = await parser.http_client.safe_request(history_url)
    if history_data:
        if "current" in history_data:
            parser.db.save_manager_history(manager_id, history_data["current"])
        if "past" in history_data:
            for past in history_data["past"]:
                # Убедимся, что team_name присутствует
                if "team_name" not in past:
                    past["team_name"] = "Unknown"
                parser.db.save_past_season(manager_id, past)

    # Добавляем лиги менеджера в очередь
    for league in data.get("leagues", {}).get("classic", []):
        league_id = league.get("id")
        if league_id and league_id not in parser.db.processed_leagues:
            parser.db.add_to_queue("league", league_id, priority=2)

    if manager_id % 100 == 0:
        logger.info(f"Обработан менеджер {manager_id}: {team_name}")
