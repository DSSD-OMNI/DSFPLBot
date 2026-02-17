import asyncio
import logging

logger = logging.getLogger(__name__)

class RangeScanStrategy:
    def __init__(self, parser):
        self.parser = parser
        self.config = parser.config["strategies"]["range_scan"]
        self.interval = self.config["interval_minutes"] * 60
        self.step = self.config.get("step", 1)
        self.priority = self.config.get("priority", 3)
        self.running = True

    async def run(self):
        while self.parser.running and self.running:
            await asyncio.sleep(self.interval)
