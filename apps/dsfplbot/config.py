import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7656545640:AAHR8FUqHZ9NxiZmnUWt2FVGdZvgB6NFpgY")
FPL_LEAGUE_ID = int(os.getenv("FPL_LEAGUE_ID", "1125782"))
DB_PATH = os.getenv("DB_PATH", "dsfpl.db")
FPL_PARSER_DB_PATH = os.getenv("FPL_PARSER_DB_PATH", "fpl_data.db")
DEADLINE = "2026-02-21 16:30:00"
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "74099420"))
CACHE_TTL = 300
