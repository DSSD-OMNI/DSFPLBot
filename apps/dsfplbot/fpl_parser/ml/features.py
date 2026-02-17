import asyncio
import logging

logger = logging.getLogger(__name__)


class MLFeatureEngine:
    def __init__(self, db):
        self.db = db

    async def recalculate_features(self):
        logger.info("Пересчёт ML-фич...")
        await asyncio.sleep(1)
        logger.info("ML-фичи пересчитаны.")

    async def periodic_recalc(self, interval_seconds: int):
        while True:
            await asyncio.sleep(interval_seconds)
            await self.recalculate_features()
