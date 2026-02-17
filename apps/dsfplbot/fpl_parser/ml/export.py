import asyncio
import pandas as pd
import json
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Exporter:
    def __init__(self, db, export_config: dict):
        self.db = db
        self.config = export_config
        self.csv_dir = Path(export_config.get("csv_dir", "exports"))
        self.csv_dir.mkdir(exist_ok=True)

    async def export_all(self):
        with self.db.connect() as conn:
            for table in ["leagues", "managers", "league_standings", "manager_history", "ml_features"]:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                df.to_csv(self.csv_dir / f"{table}_{datetime.now():%Y%m%d}.csv", index=False)
        logger.info(f"Экспорт завершён в {self.csv_dir}")

    async def export_ml_dataset(self, format: str = "jsonl"):
        with self.db.connect() as conn:
            query = """
                SELECT ls.*, mh.points, mh.overall_rank, m.player_name, m.team_name
                FROM league_standings ls
                LEFT JOIN manager_history mh ON ls.entry_id = mh.entry_id AND ls.event = mh.event
                LEFT JOIN managers m ON ls.entry_id = m.manager_id
            """
            df = pd.read_sql_query(query, conn)
            if format == "jsonl":
                df.to_json(self.config["jsonl_file"], orient="records", lines=True)
            elif format == "parquet":
                df.to_parquet(self.config["parquet_file"], index=False)
        logger.info(f"ML-датасет сохранён")

    async def scheduled_export(self, hour: int):
        while True:
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run = next_run.replace(day=next_run.day + 1)
            sleep_seconds = (next_run - now).total_seconds()
            await asyncio.sleep(sleep_seconds)
            await self.export_all()
            await self.export_ml_dataset("jsonl")
