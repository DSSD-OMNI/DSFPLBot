import aiosqlite
from apps.dsfplbot.config import FPL_PARSER_DB_PATH

async def get_latest_league_standings(league_id: int):
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT scraped_at FROM league_standings WHERE league_id = ? ORDER BY scraped_at DESC LIMIT 1",
            (league_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        scraped_at = row[0]
        cursor = await conn.execute("""
            SELECT ls.*, m.team_name AS manager_name
            FROM league_standings ls
            LEFT JOIN managers m ON ls.entry_id = m.manager_id
            WHERE ls.league_id = ? AND ls.scraped_at = ?
            ORDER BY ls.rank
        """, (league_id, scraped_at))
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

async def get_manager_history(entry_id: int):
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT * FROM manager_history WHERE entry_id = ? ORDER BY event",
            (entry_id,)
        )
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

async def get_manager_info(entry_id: int):
    async with aiosqlite.connect(FPL_PARSER_DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT * FROM managers WHERE manager_id = ?",
            (entry_id,)
        )
        row = await cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
from apps.dsfplbot.fpl_api import get_current_event
