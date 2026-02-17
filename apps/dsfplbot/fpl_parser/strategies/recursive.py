from datetime import datetime, timedelta
from datetime import datetime, timedelta
import asyncio
import logging

from ..handlers.league import fetch_league
from ..handlers.manager import fetch_manager

logger = logging.getLogger(__name__)


class RecursiveCrawlStrategy:
    def __init__(self, parser):
        self.parser = parser
        self.config = parser.config["strategies"]["recursive"]
        self.workers_count = self.config.get("workers", 10)
        self.max_iterations = self.config.get("max_iterations", 1000)
        self.interval = self.config["interval_minutes"] * 60
        self.running = True

    async def worker(self, worker_id):
        """Один воркер, берущий задачи из очереди и обрабатывающий их."""
        logger.info(f"Воркер {worker_id} запущен")
        while self.parser.running and self.running:
            task = self.parser.db.get_next_task()
            if not task:
                await asyncio.sleep(5)
                continue
            item_type, item_id, priority = task
            try:
                if item_type == "league":
                    await fetch_league(self.parser, item_id)
                    # Планируем следующее обновление через 6 часов
                    next_attempt = (datetime.now() + timedelta(hours=6)).isoformat()
                    self.parser.db.add_to_queue("league", item_id, priority=priority, next_attempt=next_attempt)
                elif item_type == "manager":
                    await fetch_manager(self.parser, item_id)
                    # Планируем следующее обновление через 24 часа
                    next_attempt = (datetime.now() + timedelta(hours=24)).isoformat()
                    self.parser.db.add_to_queue("manager", item_id, priority=priority, next_attempt=next_attempt)
            except Exception as e:
                logger.error(f"Ошибка обработки {item_type}:{item_id}: {e}")
                self.parser.db.mark_for_retry(item_type, item_id, str(e))
        logger.info(f"Воркер {worker_id} завершён")

    async def run(self):
        """Запускает пул воркеров и периодически перезапускает их (или просто держит работающими)."""
        from datetime import datetime, timedelta  # добавим импорт здесь
        workers = []
        for i in range(self.workers_count):
            workers.append(asyncio.create_task(self.worker(i)))
        await asyncio.gather(*workers)
