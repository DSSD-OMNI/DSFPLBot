import aiohttp
import asyncio
import logging
import random
from typing import Optional, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiohttp import ClientError, ClientResponseError

from .rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)


class HTTPClient:
    def __init__(self, config: dict):
        self.config = config
        self.proxies = config.get("proxies", [])
        self.user_agents = config.get("user_agents", [])
        self.rate_limiter = AdaptiveRateLimiter(config.get("rate_limit", {}))
        self.session_pool = {}
        self._current_proxy_index = 0

    def _get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._current_proxy_index % len(self.proxies)]
        self._current_proxy_index += 1
        return proxy

    def _get_random_ua(self) -> str:
        return random.choice(self.user_agents) if self.user_agents else "Mozilla/5.0"

    async def _create_session(self) -> aiohttp.ClientSession:
        """Создаёт новую сессию с текущими прокси и заголовками."""
        headers = {
            "User-Agent": self._get_random_ua(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://fantasy.premierleague.com/"
        }
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, use_dns_cache=True)
        return aiohttp.ClientSession(headers=headers, connector=connector)

    async def get_session(self) -> aiohttp.ClientSession:
        """Возвращает сессию из пула или создаёт новую."""
        return await self._create_session()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((ClientError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(f"Повторная попытка {retry_state.attempt_number} после ошибки: {retry_state.outcome.exception()}")
    )
    async def safe_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Выполняет HTTP-запрос с адаптивным ожиданием и повторными попытками."""
        await self.rate_limiter.wait_if_needed()

        session = await self.get_session()
        proxy = self._get_next_proxy()
        try:
            async with session.get(url, params=params, proxy=proxy, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.rate_limiter.update_delay(success=True)
                    return data
                elif resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit (429). Ждём {retry_after} сек.")
                    await asyncio.sleep(retry_after)
                    self.rate_limiter.update_delay(success=False)
                    raise ClientResponseError(resp.request_info, resp.history, status=resp.status)
                elif resp.status == 404:
                    self.rate_limiter.update_delay(success=True)
                    return None
                else:
                    logger.error(f"HTTP {resp.status} для {url}")
                    self.rate_limiter.update_delay(success=False)
                    resp.raise_for_status()
        except (asyncio.TimeoutError, ClientError) as e:
            logger.warning(f"Ошибка запроса: {e}")
            self.rate_limiter.update_delay(success=False)
            raise
        finally:
            await session.close()

        return None

    async def close(self):
        """Закрывает все сессии."""
        pass
