import asyncio
import time
import random
from collections import deque
from typing import Dict


class AdaptiveRateLimiter:
    def __init__(self, config: dict):
        self.base_delay = config.get("base_delay", 0.5)
        self.min_delay = config.get("min_delay", 0.2)
        self.max_delay = config.get("max_delay", 10.0)
        self.backoff_factor = config.get("backoff_factor", 2.0)
        self.success_window = config.get("success_window", 50)
        self.error_threshold = config.get("error_threshold", 0.1)

        self.current_delay = self.base_delay
        self.last_request_time = 0
        self.success_history = deque(maxlen=self.success_window)
        self.consecutive_errors = 0
        self.lock = asyncio.Lock()

    async def wait_if_needed(self):
        """Ожидание перед следующим запросом, если необходимо."""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.current_delay:
                sleep_time = self.current_delay - elapsed
                await asyncio.sleep(sleep_time)

    def update_delay(self, success: bool):
        """Обновляет текущую задержку на основе успешности запроса."""
        self.success_history.append(1 if success else 0)
        self.last_request_time = time.time()

        if not success:
            self.consecutive_errors += 1
            self.current_delay = min(
                self.current_delay * self.backoff_factor,
                self.max_delay
            )
        else:
            self.consecutive_errors = 0
            if len(self.success_history) == self.success_window:
                success_rate = sum(self.success_history) / self.success_window
                if success_rate > 0.95:
                    self.current_delay = max(
                        self.current_delay / 1.2,
                        self.min_delay
                    )
                elif success_rate < self.error_threshold:
                    self.current_delay = min(
                        self.current_delay * 1.5,
                        self.max_delay
                    )
            jitter = random.uniform(0.9, 1.1)
            self.current_delay *= jitter

    def get_stats(self) -> Dict:
        return {
            "current_delay": self.current_delay,
            "consecutive_errors": self.consecutive_errors,
            "success_rate": sum(self.success_history) / len(self.success_history) if self.success_history else 1.0,
        }
