"""
Чтение данных из БД парсера (fpl_data.db).
Парсер DSDeepParser заполняет таблицы:
  - league_standings_{LEAGUE_ID} — текущая таблица лиги
  - features — признаки менеджеров (form_5gw, lri и др.)
  - lri_scores — LRI по турам
  - bootstrap — общие данные FPL
"""
import logging
from typing import Optional, List, Dict, Any

import aiosqlite

from apps.dsfplbot.config import FPL_PARSER_DB_PATH, PARSER_STANDINGS_TABLE

logger = logging.getLogger(__name__)


async def _table_exists(db: aiosqlite.Connection, table_name: str) -> bool:
    """Проверяет, существует ли таблица в БД."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return (await cursor.fetchone()) is not None


async def get_parser_tables() -> List[str]:
    """Возвращает список всех таблиц в БД парсера (для диагностики)."""
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Cannot read parser DB tables: {e}")
        return []


async def get_latest_league_standings(league_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Читает текущую таблицу лиги из parser DB.
    Таблица: league_standings_{league_id}
    """
    table_name = f"league_standings_{league_id}"
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            if not await _table_exists(db, table_name):
                logger.warning(f"Table {table_name} not found in parser DB")
                return None

            cursor = await db.execute(f"SELECT * FROM [{table_name}] ORDER BY rank")
            rows = await cursor.fetchall()
            if not rows:
                return None
            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in rows]
            logger.debug(f"Read {len(result)} rows from {table_name}")
            return result
    except Exception as e:
        logger.error(f"Error reading {table_name}: {e}")
        return None


async def get_lri_scores(entry_id: int = None, event: int = None) -> List[Dict[str, Any]]:
    """
    Читает LRI из таблицы lri_scores.
    Опционально фильтрует по entry_id и/или event.
    """
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            if not await _table_exists(db, "lri_scores"):
                logger.warning("Table lri_scores not found")
                return []

            query = "SELECT * FROM lri_scores WHERE 1=1"
            params = []
            if entry_id is not None:
                query += " AND entry_id = ?"
                params.append(entry_id)
            if event is not None:
                query += " AND event = ?"
                params.append(event)
            query += " ORDER BY event DESC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error reading lri_scores: {e}")
        return []


async def get_latest_lri_for_entry(entry_id: int) -> Optional[float]:
    """Возвращает последний LRI для менеджера."""
    scores = await get_lri_scores(entry_id=entry_id)
    if scores:
        return scores[0].get("lri", 5.0)
    return None


async def get_features(entry_id: int = None, event: int = None) -> List[Dict[str, Any]]:
    """
    Читает features (form_5gw, lri и др.) из таблицы features.
    """
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            if not await _table_exists(db, "features"):
                logger.warning("Table features not found")
                return []

            query = "SELECT * FROM features WHERE 1=1"
            params = []
            if entry_id is not None:
                query += " AND entry_id = ?"
                params.append(entry_id)
            if event is not None:
                query += " AND event = ?"
                params.append(event)
            query += " ORDER BY event DESC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error reading features: {e}")
        return []


async def get_form_for_entry(entry_id: int, event: int = None) -> Optional[float]:
    """
    Возвращает form_5gw (средние очки за 5 туров) для менеджера.
    Используется как fallback, когда нет manager_history.
    """
    features = await get_features(entry_id=entry_id, event=event)
    if features:
        return features[0].get("form_5gw")
    return None


async def get_manager_history(entry_id: int) -> List[Dict[str, Any]]:
    """
    Пытается прочитать историю менеджера из parser DB.
    Таблица manager_history может отсутствовать — вернём пустой список.
    """
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            if not await _table_exists(db, "manager_history"):
                logger.debug("Table manager_history not found — using fallback")
                return []

            cursor = await db.execute(
                "SELECT * FROM manager_history WHERE entry_id = ? ORDER BY event",
                (entry_id,)
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error reading manager_history for {entry_id}: {e}")
        return []


async def get_current_event_from_parser() -> Optional[int]:
    """Пытается определить текущий тур из данных парсера."""
    try:
        async with aiosqlite.connect(FPL_PARSER_DB_PATH) as db:
            # Пробуем из lri_scores
            if await _table_exists(db, "lri_scores"):
                cursor = await db.execute("SELECT MAX(event) FROM lri_scores")
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]

            # Пробуем из features
            if await _table_exists(db, "features"):
                cursor = await db.execute("SELECT MAX(event) FROM features")
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        return None
    except Exception as e:
        logger.error(f"Error getting current event from parser: {e}")
        return None
