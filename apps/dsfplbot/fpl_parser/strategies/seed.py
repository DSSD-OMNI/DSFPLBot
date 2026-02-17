import logging

logger = logging.getLogger(__name__)


class SeedStrategy:
    def __init__(self, parser):
        self.parser = parser
        self.config = parser.config["strategies"]["seed"]
        self.priority = self.config.get("priority", 0)

    async def run(self):
        """Добавляет начальные лиги и менеджеров в очередь (однократно при старте)."""
        leagues = self.config.get("leagues", [])
        managers = self.config.get("managers", [])
        for league_id in leagues:
            self.parser.db.add_to_queue("league", league_id, priority=self.priority)
        for manager_id in managers:
            self.parser.db.add_to_queue("manager", manager_id, priority=self.priority)
        logger.info(f"Seed: добавлено {len(leagues)} лиг и {len(managers)} менеджеров")
        return
