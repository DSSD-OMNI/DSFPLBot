import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "dsfpl.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_fpl (
                user_id INTEGER PRIMARY KEY,
                fpl_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                user_id INTEGER,
                game TEXT,
                score INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, game)
            )
        ''')
        await db.commit()

async def save_user_fpl_id(user_id: int, fpl_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_fpl (user_id, fpl_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, fpl_id))
        await db.commit()

async def get_user_fpl_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT fpl_id FROM user_fpl WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def add_score(user_id: int, game: str, points: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO scores (user_id, game, score, attempts)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, game) DO UPDATE SET
                score = score + ?,
                attempts = attempts + 1,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, game, points, points))
        await db.commit()

async def get_scores(game: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if game:
            cursor = await db.execute('''
                SELECT user_id, score, attempts FROM scores
                WHERE game = ?
                ORDER BY score DESC
                LIMIT 10
            ''', (game,))
        else:
            cursor = await db.execute('''
                SELECT user_id, SUM(score) as total_score, SUM(attempts) as total_attempts
                FROM scores
                GROUP BY user_id
                ORDER BY total_score DESC
                LIMIT 10
            ''')
        rows = await cursor.fetchall()
        return rows
async def import_legacy_csv(csv_path: str):
    """Заглушка для импорта CSV. Реализация будет позже."""
    pass
