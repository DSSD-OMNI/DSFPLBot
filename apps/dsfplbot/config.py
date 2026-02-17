import os

# Токен Telegram бота (обязательно)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7656545640:AAHR8FUqHZ9NxiZmnUWt2FVGdZvgB6NFpgY")

# ID вашей лиги FPL
FPL_LEAGUE_ID = int(os.getenv("FPL_LEAGUE_ID", "1125782"))

# Ваш Telegram ID для административных команд
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "74099420"))

# Пути к базам данных (используются в volume)
DB_PATH = os.getenv("DB_PATH", "dsfpl.db")
FPL_PARSER_DB_PATH = os.getenv("FPL_PARSER_DB_PATH", "fpl_data.db")

# Дедлайн для отсчёта времени (можно оставить как есть)
DEADLINE = "2026-02-21 16:30:00+03:00"

# Время жизни кэша
CACHE_TTL = 300

# Проверка импорта (добавлено для версии 2)
print("config.py loaded successfully", flush=True)
