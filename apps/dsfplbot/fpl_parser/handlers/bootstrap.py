async def fetch_bootstrap(parser):
    """Получает статические данные (игроки, команды, текущая GW)."""
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    data = await parser.http_client.safe_request(url)
    return data
