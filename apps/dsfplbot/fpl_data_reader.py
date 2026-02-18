import aiosqlite
import os

FPL_PARSER_DB_PATH = os.getenv("FPL_PARSER_DB_PATH", "/data/fpl_data.db")

async def get_latest_league_standings(league_id: int):
    """Возвращает текущую таблицу лиги из таблицы league_standings_<league_id>."""
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        table_name = f"league_standings_{league_id}"
        async with db.execute(f"SELECT entry_id, player_name, total_points, rank, last_rank, event_points FROM {table_name} ORDER BY rank") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_lri_for_entry(entry_id: int, event: int = None) -> float:
    """Возвращает последний доступный LRI для менеджера."""
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
        if event is None:
            async with db.execute(
                "SELECT lri FROM lri_scores WHERE entry_id = ? ORDER BY event DESC LIMIT 1",
                (entry_id,)
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with db.execute(
                "SELECT lri FROM lri_scores WHERE entry_id = ? AND event = ?",
                (entry_id, event)
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else 5.0

async def get_form_for_entry(entry_id: int, weeks: int = 5) -> float:
    """
    Возвращает среднюю форму за последние weeks туров.
    Пока используем поле form_5gw из таблицы features как приближение.
    """
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
        async with db.execute(
            "SELECT form_5gw FROM features WHERE entry_id = ? ORDER BY event DESC LIMIT 1",
            (entry_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0
