#!/usr/bin/env python3
"""
FPL Ultimate Parser - 24/7 Production-ready parser with ML feature engineering.
"""

import asyncio
import logging
import signal
from datetime import datetime

from database import Database
from http_client import HTTPClient
from strategies.range_scan import RangeScanStrategy
from strategies.recursive import RecursiveCrawlStrategy
from strategies.seed import SeedStrategy
from strategies.best_leagues import BestLeaguesStrategy
from ml.features import MLFeatureEngine
from ml.export import Exporter
from utils import setup_logging, load_config

logger = logging.getLogger(__name__)


class FPLUltimateParser:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.db = Database(self.config["database"]["path"])
        self.http_client = HTTPClient(self.config)
        self.running = True

        # Инициализация стратегий
        self.strategies = []
        if self.config["strategies"]["range_scan"]["enabled"]:
            self.strategies.append(RangeScanStrategy(self))
        if self.config["strategies"]["recursive"]["enabled"]:
            self.strategies.append(RecursiveCrawlStrategy(self))
        if self.config["strategies"]["seed"]["enabled"]:
            self.strategies.append(SeedStrategy(self))
        if self.config["strategies"]["best_leagues"]["enabled"]:
            self.strategies.append(BestLeaguesStrategy(self))

        # ML модуль
        self.ml_engine = MLFeatureEngine(self.db) if self.config["ml"]["enabled"] else None
        self.exporter = Exporter(self.db, self.config["export"])

        # Статистика
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "leagues_found": 0,
            "managers_found": 0,
            "start_time": datetime.now(),
        }

        # Загрузка обработанных ID
        self.db.load_processed_ids()

    async def run_24_7(self):
        """Главный цикл работы парсера."""
        logger.info("🚀 Запуск FPL Ultimate Parser 24/7")

        # Запуск стратегий как фоновых задач
        tasks = []
        for strategy in self.strategies:
            tasks.append(asyncio.create_task(strategy.run()))

        # Запуск воркеров рекурсивного обхода (они уже внутри стратегии RecursiveCrawlStrategy)
        if self.ml_engine:
            tasks.append(asyncio.create_task(self.ml_engine.periodic_recalc(
                self.config["ml"]["recalculate_interval_hours"] * 3600
            )))

        # Задача экспорта по расписанию
        tasks.append(asyncio.create_task(self.exporter.scheduled_export(
            self.config["export"]["schedule_hour"]
        )))

        # Задача сохранения статистики (каждые 10 минут)
        tasks.append(asyncio.create_task(self.periodic_stats_save()))

        # Ожидание завершения
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Парсер остановлен.")
            await self.shutdown()
            raise
        finally:
            await self.shutdown()

    async def periodic_stats_save(self):
        """Сохранение статистики в БД каждые 10 минут."""
        while self.running:
            await asyncio.sleep(600)
            self.stats["uptime"] = (datetime.now() - self.stats["start_time"]).total_seconds()
            await self.db.save_stats(self.stats)
            logger.info(f"Статистика сохранена: {self.stats}")

    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("Завершение работы парсера...")
        self.running = False
        # Останавливаем все стратегии
        for strategy in self.strategies:
            if hasattr(strategy, 'running'):
                strategy.running = False
        # Закрываем соединения
        await self.http_client.close()
        await self.db.close()
        logger.info("Парсер завершён.")


async def main():
    parser = FPLUltimateParser()
    await parser.run_24_7()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
