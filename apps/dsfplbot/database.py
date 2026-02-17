from typing import Optional
import aiosqlite
import logging
logger = logging.getLogger(__name__)
import json
from apps.dsfplbot.config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                fpl_entry_id INTEGER,
                notifications_enabled INTEGER DEFAULT 0,
                deadline_reminders INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS fpl_links (
                telegram_id INTEGER PRIMARY KEY,
                fpl_entry_id INTEGER UNIQUE,
                verified INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS manager_past_seasons (
                entry_id INTEGER,
                season TEXT,
                total_points INTEGER,
                rank INTEGER,
                team_name TEXT,
                PRIMARY KEY (entry_id, season)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS halloffame_legacy (
                season TEXT,
                pos INTEGER,
                manager TEXT,
                team TEXT,
                total_points INTEGER,
                overall_rank INTEGER,
                verified INTEGER DEFAULT 0,
                PRIMARY KEY (season, pos)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quiz_scores (
                user_id INTEGER,
                game_type TEXT,
                score INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game_type)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quiz_answers (
                user_id INTEGER,
                question_date TEXT,
                question_idx INTEGER,
                answer TEXT,
                correct INTEGER,
                PRIMARY KEY (user_id, question_date, question_idx)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gtd_predictions (
                user_id INTEGER,
                event INTEGER,
                player_id INTEGER,
                predicted_goal INTEGER DEFAULT 0,
                actual_goal INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, player_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS match_predictions (
                user_id INTEGER,
                event INTEGER,
                fixture_id INTEGER,
                prediction TEXT,
                result TEXT,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, fixture_id)
            )
        ''')
        await db.commit()

async def get_user_fpl_id(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT fpl_entry_id FROM fpl_links WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def save_user_fpl_id(telegram_id: int, fpl_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO fpl_links (telegram_id, fpl_entry_id) VALUES (?, ?)", (telegram_id, fpl_id))
        await db.commit()

async def get_notifications_enabled(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT notifications_enabled FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else False

async def set_notifications_enabled(telegram_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO users (telegram_id, notifications_enabled) VALUES (?, ?)", (telegram_id, int(enabled)))
        await db.commit()

async def get_deadline_reminders(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT deadline_reminders FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else False

async def set_deadline_reminders(telegram_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO users (telegram_id, deadline_reminders) VALUES (?, ?)", (telegram_id, int(enabled)))
        await db.commit()

async def get_api_season(season: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT entry_id, season, total_points, rank, team_name FROM manager_past_seasons WHERE season = ? ORDER BY rank ASC",
            (season,)
        )
        rows = await cursor.fetchall()
        return [{"entry_id": r[0], "season": r[1], "total_points": r[2], "rank": r[3], "team_name": r[4]} for r in rows]

async def get_legacy_season(season: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT season, pos, manager, team, total_points, overall_rank, verified FROM halloffame_legacy WHERE season = ? ORDER BY pos ASC",
            (season,)
        )
        rows = await cursor.fetchall()
        return [{"season": r[0], "pos": r[1], "manager": r[2], "team": r[3], "total_points": r[4], "overall_rank": r[5], "verified": r[6]} for r in rows]

async def import_legacy_csv(csv_path):
    import csv
    async with aiosqlite.connect(DB_PATH) as db:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                await db.execute(
                    "INSERT OR IGNORE INTO halloffame_legacy (season, pos, manager, team, total_points, overall_rank) VALUES (?, ?, ?, ?, ?, ?)",
                    (row["Season"], row["Pos"], row["Manager"], row["Team"], row["Total Points"], row["Overall Rank"])
                )
        await db.commit()

# ----- Таблицы для игр -----
async def init_games_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # Ответы на DoubleQuiz
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quiz_answers (
                user_id INTEGER,
                question_date TEXT,
                question_idx INTEGER,
                answer TEXT,
                correct INTEGER,
                PRIMARY KEY (user_id, question_date, question_idx)
            )
        ''')
        # Прогнозы GTD
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gtd_predictions (
                user_id INTEGER,
                event INTEGER,
                player_id INTEGER,
                predicted INTEGER DEFAULT 0,
                actual INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, player_id)
            )
        ''')
        # Прогнозы на матчи
        await db.execute('''
            CREATE TABLE IF NOT EXISTS match_predictions (
                user_id INTEGER,
                event INTEGER,
                fixture_id INTEGER,
                prediction TEXT,
                result TEXT,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, fixture_id)
            )
        ''')
        # Очки пользователей в играх
        await db.execute('''
            CREATE TABLE IF NOT EXISTS game_scores (
                user_id INTEGER,
                game TEXT,
                score INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game)
            )
        ''')
        await db.commit()

# Функции для работы с очками
async def add_score(user_id: int, game: str, points: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO game_scores (user_id, game, score, total)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, game) DO UPDATE SET
                score = score + ?,
                total = total + 1
        ''', (user_id, game, points, points))
        await db.commit()

async def get_scores(game: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if game:
            cursor = await db.execute('''
                SELECT user_id, score, total FROM game_scores WHERE game = ? ORDER BY score DESC
            ''', (game,))
        else:
            cursor = await db.execute('''
                SELECT user_id, SUM(score) as score, SUM(total) as total FROM game_scores GROUP BY user_id ORDER BY score DESC
            ''')
        rows = await cursor.fetchall()
        return rows

async def init_fpl_links_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS fpl_links (
                telegram_id INTEGER PRIMARY KEY,
                fpl_entry_id INTEGER UNIQUE,
                verified INTEGER DEFAULT 0
            )
        ''')
        await db.commit()

async def save_user_fpl_id(telegram_id: int, fpl_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO fpl_links (telegram_id, fpl_entry_id)
            VALUES (?, ?)
        ''', (telegram_id, fpl_id))
        await db.commit()
        logger.info(f"Saved FPL ID {fpl_id} for user {telegram_id}")

async def get_user_fpl_id(telegram_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT fpl_entry_id FROM fpl_links WHERE telegram_id = ?', (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

# ----- Таблицы для игр -----
async def init_games_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quiz_answers (
                user_id INTEGER,
                question_date TEXT,
                question_idx INTEGER,
                answer TEXT,
                correct INTEGER,
                PRIMARY KEY (user_id, question_date, question_idx)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gtd_predictions (
                user_id INTEGER,
                event INTEGER,
                player_id INTEGER,
                predicted INTEGER DEFAULT 0,
                actual INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, player_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS match_predictions (
                user_id INTEGER,
                event INTEGER,
                fixture_id INTEGER,
                prediction TEXT,
                result TEXT,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, event, fixture_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS game_scores (
                user_id INTEGER,
                game TEXT,
                score INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game)
            )
        ''')
        await db.commit()

async def add_score(user_id: int, game: str, points: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO game_scores (user_id, game, score, total)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, game) DO UPDATE SET
                score = score + ?,
                total = total + 1
        ''', (user_id, game, points, points))
        await db.commit()

async def get_scores(game: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if game:
            cursor = await db.execute('''
                SELECT user_id, score, total FROM game_scores WHERE game = ? ORDER BY score DESC
            ''', (game,))
        else:
            cursor = await db.execute('''
                SELECT user_id, SUM(score) as score, SUM(total) as total FROM game_scores GROUP BY user_id ORDER BY score DESC
            ''')
        rows = await cursor.fetchall()
        return rows
