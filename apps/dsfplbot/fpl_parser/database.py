import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Set
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
        self.processed_leagues: Set[int] = set()
        self.processed_managers: Set[int] = set()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Создание всех таблиц."""
        with self.connect() as conn:
            cursor = conn.cursor()

            # leagues
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leagues (
                    league_id INTEGER PRIMARY KEY,
                    name TEXT,
                    season TEXT,
                    created_epoch INTEGER,
                    entry_count INTEGER,
                    admin_entry INTEGER,
                    last_scraped TIMESTAMP,
                    scrape_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')

            # managers
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS managers (
                    manager_id INTEGER PRIMARY KEY,
                    player_name TEXT,
                    team_name TEXT,
                    region TEXT,
                    overall_rank INTEGER,
                    last_scraped TIMESTAMP
                )
            ''')

            # league_standings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS league_standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id INTEGER,
                    entry_id INTEGER,
                    event INTEGER,
                    rank INTEGER,
                    total_points INTEGER,
                    event_points INTEGER,
                    transfers INTEGER,
                    transfers_cost INTEGER,
                    percentile REAL,
                    gw_position REAL,
                    scraped_at TIMESTAMP,
                    FOREIGN KEY(league_id) REFERENCES leagues(league_id),
                    FOREIGN KEY(entry_id) REFERENCES managers(manager_id)
                )
            ''')

            # manager_history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS manager_history (
                    entry_id INTEGER,
                    event INTEGER,
                    points INTEGER,
                    total_points INTEGER,
                    rank INTEGER,
                    overall_rank INTEGER,
                    bank INTEGER,
                    value INTEGER,
                    transfers INTEGER,
                    transfers_cost INTEGER,
                    active_chip TEXT,
                    PRIMARY KEY (entry_id, event)
                )
            ''')

            # manager_past_seasons
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS manager_past_seasons (
                    entry_id INTEGER,
                    season TEXT,
                    total_points INTEGER,
                    rank INTEGER,
                    team_name TEXT,
                    PRIMARY KEY (entry_id, season)
                )
            ''')

            # processing_queue
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_queue (
                    item_type TEXT,
                    item_id INTEGER,
                    priority INTEGER,
                    next_attempt TIMESTAMP,
                    attempt_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    PRIMARY KEY (item_type, item_id)
                )
            ''')

            # scraper_stats
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraper_stats (
                    timestamp TIMESTAMP PRIMARY KEY,
                    requests_made INTEGER,
                    successful_requests INTEGER,
                    failed_requests INTEGER,
                    leagues_found INTEGER,
                    managers_found INTEGER,
                    avg_delay REAL,
                    uptime_seconds INTEGER
                )
            ''')

            # ml_features
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_features (
                    entry_id INTEGER,
                    league_id INTEGER,
                    season TEXT,
                    avg_gw_points REAL,
                    total_transfers REAL,
                    transfer_efficiency REAL,
                    captain_consistency REAL,
                    risk_score REAL,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (entry_id, league_id, season)
                )
            ''')

            # Индексы для ускорения
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_standings_league ON league_standings(league_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_standings_entry ON league_standings(entry_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_entry ON manager_history(entry_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_next ON processing_queue(next_attempt)')

    def load_processed_ids(self):
        """Загружает уже обработанные ID из БД."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT league_id FROM leagues")
            self.processed_leagues = {row["league_id"] for row in cursor.fetchall()}
            cursor.execute("SELECT manager_id FROM managers")
            self.processed_managers = {row["manager_id"] for row in cursor.fetchall()}
        logger.info(f"Загружено лиг: {len(self.processed_leagues)}, менеджеров: {len(self.processed_managers)}")

    # Методы для работы с очередью
    def add_to_queue(self, item_type: str, item_id: int, priority: int = 5, next_attempt: str = None):
        """Добавляет задачу в очередь (или обновляет, если уже есть)."""
        if next_attempt is None:
            next_attempt = datetime.now().isoformat()
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processing_queue
                (item_type, item_id, priority, next_attempt, attempt_count, last_error)
                VALUES (?, ?, ?, ?, COALESCE((SELECT attempt_count+1 FROM processing_queue WHERE item_type=? AND item_id=?), 0), NULL)
            ''', (item_type, item_id, priority, next_attempt, item_type, item_id))

    def get_next_task(self):
        """Возвращает следующую задачу для выполнения (с учётом приоритета и времени)."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_type, item_id, priority FROM processing_queue
                WHERE datetime(next_attempt) <= datetime(?)
                ORDER BY priority ASC, attempt_count ASC
                LIMIT 1
            ''', (datetime.now().isoformat(),))
            row = cursor.fetchone()
            if row:
                cursor.execute('DELETE FROM processing_queue WHERE item_type=? AND item_id=?', (row["item_type"], row["item_id"]))
                return row["item_type"], row["item_id"], row["priority"]
        return None

    def mark_for_retry(self, item_type: str, item_id: int, error_msg: str):
        """Помечает задачу для повторной попытки с экспоненциальной задержкой."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT attempt_count FROM processing_queue
                WHERE item_type=? AND item_id=?
            ''', (item_type, item_id))
            row = cursor.fetchone()
            attempt = (row["attempt_count"] if row else 0) + 1
            delay_minutes = 5 * (2 ** (attempt - 1))
            next_attempt = (datetime.now() + timedelta(minutes=delay_minutes)).isoformat()
            cursor.execute('''
                INSERT OR REPLACE INTO processing_queue
                (item_type, item_id, priority, next_attempt, attempt_count, last_error)
                VALUES (?, ?, (SELECT priority FROM processing_queue WHERE item_type=? AND item_id=?), ?, ?, ?)
            ''', (item_type, item_id, item_type, item_id, next_attempt, attempt, error_msg[:200]))

    # Методы сохранения данных
    def save_league(self, league_data: dict):
        """Сохраняет информацию о лиге."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO leagues
                (league_id, name, season, created_epoch, entry_count, admin_entry, last_scraped, scrape_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT scrape_count+1 FROM leagues WHERE league_id=?), 0), ?)
            ''', (
                league_data["league_id"],
                league_data.get("name"),
                league_data.get("season"),
                league_data.get("created_epoch"),
                league_data.get("entry_count"),
                league_data.get("admin_entry"),
                datetime.now().isoformat(),
                league_data["league_id"],
                json.dumps(league_data.get("metadata", {}))
            ))
            self.processed_leagues.add(league_data["league_id"])

    def save_league_standings(self, league_id: int, standings: List[dict], event: int):
        """Сохраняет позиции участников лиги с рассчитанными признаками."""
        with self.connect() as conn:
            cursor = conn.cursor()
            total = len(standings)
            for entry in standings:
                rank = entry["rank"]
                percentile = (rank - 1) / (total - 1) if total > 1 else 0
                gw_position = entry.get("event_points", 0) / max(entry.get("total_points", 1), 1)
                cursor.execute('''
                    INSERT INTO league_standings
                    (league_id, entry_id, event, rank, total_points, event_points, transfers, transfers_cost, percentile, gw_position, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    league_id,
                    entry["entry_id"],
                    event,
                    rank,
                    entry.get("total_points"),
                    entry.get("event_points"),
                    entry.get("transfers", 0),
                    entry.get("transfers_cost", 0),
                    percentile,
                    gw_position,
                    datetime.now().isoformat()
                ))

    def save_manager(self, manager_data: dict):
        """Сохраняет информацию о менеджере."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO managers
                (manager_id, player_name, team_name, region, overall_rank, last_scraped)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                manager_data["manager_id"],
                manager_data.get("player_name"),
                manager_data.get("team_name"),
                manager_data.get("region"),
                manager_data.get("overall_rank"),
                datetime.now().isoformat()
            ))
            self.processed_managers.add(manager_data["manager_id"])

    def save_manager_history(self, entry_id: int, history: List[dict]):
        """Сохраняет историю менеджера по игровым неделям."""
        with self.connect() as conn:
            cursor = conn.cursor()
            for gw in history:
                cursor.execute('''
                    INSERT OR REPLACE INTO manager_history
                    (entry_id, event, points, total_points, rank, overall_rank, bank, value, transfers, transfers_cost, active_chip)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry_id,
                    gw["event"],
                    gw.get("points"),
                    gw.get("total_points"),
                    gw.get("rank"),
                    gw.get("overall_rank"),
                    gw.get("bank"),
                    gw.get("value"),
                    gw.get("transfers", 0),
                    gw.get("transfers_cost", 0),
                    gw.get("active_chip")
                ))

    def save_past_season(self, entry_id: int, past: dict):
        """Сохраняет данные о прошлом сезоне менеджера."""
        with self.connect() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO manager_past_seasons
                (entry_id, season, total_points, rank, team_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (entry_id, past["season_name"], past["total_points"], past["rank"], past["team_name"]))

    async def save_stats(self, stats: dict):
        """Сохраняет статистику работы парсера."""
        with self.connect() as conn:
            conn.execute('''
                INSERT INTO scraper_stats
                (timestamp, requests_made, successful_requests, failed_requests, leagues_found, managers_found, avg_delay, uptime_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                stats["total_requests"],
                stats["successful_requests"],
                stats["failed_requests"],
                stats["leagues_found"],
                stats["managers_found"],
                stats.get("avg_delay", 0),
                stats.get("uptime", 0)
            ))

    async def close(self):
        """Закрытие соединений."""
        pass

    def save_past_season(self, entry_id: int, past: dict):
        """Сохраняет данные о прошлом сезоне менеджера."""
        with self.connect() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO manager_past_seasons
                (entry_id, season, total_points, rank, team_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (entry_id, past["season_name"], past["total_points"], past["rank"], past.get("team_name", "Unknown")))
