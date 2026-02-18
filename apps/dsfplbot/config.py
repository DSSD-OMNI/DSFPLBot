"""
Конфигурация DSFPLBot.
Все настройки читаются из переменных окружения.
"""
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
FPL_LEAGUE_ID = int(os.getenv("FPL_LEAGUE_ID", "1125782"))
DB_PATH = os.getenv("DB_PATH", "/data/dsfpl.db")
FPL_PARSER_DB_PATH = os.getenv("FPL_PARSER_DB_PATH", "/data/fpl_data.db")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "74099420"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

# Имя таблицы standings в БД парсера формируется как league_standings_{LEAGUE_ID}
PARSER_STANDINGS_TABLE = f"league_standings_{FPL_LEAGUE_ID}"
