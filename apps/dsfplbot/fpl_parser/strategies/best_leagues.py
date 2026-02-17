import asyncio
import logging

logger = logging.getLogger(__name__)

class BestLeaguesStrategy:
    def __init__(self, parser):
        self.parser = parser
        self.config = parser.config["strategies"]["best_leagues"]
        self.interval = self.config["interval_minutes"] * 60
        self.priority = self.config.get("priority", 0)
        self.running = True

    async def run(self):
        while self.parser.running and self.running:
            await asyncio.sleep(self.interval)
