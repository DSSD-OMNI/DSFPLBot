import aiohttp
import asyncio
import logging
from datetime import datetime
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiohttp import ClientError, ClientResponseError
from apps.dsfplbot.cache import cached
from apps.dsfplbot.config import CACHE_TTL

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ClientError, asyncio.TimeoutError, ClientResponseError)),
    before_sleep=lambda retry_state: logger.warning(f"Retry {retry_state.attempt_number} after {retry_state.outcome.exception()}")
)
async def safe_request(url: str, session: aiohttp.ClientSession = None) -> dict:
    if session is None:
        async with aiohttp.ClientSession() as sess:
            return await _request(url, sess)
    else:
        return await _request(url, session)

async def _request(url: str, session: aiohttp.ClientSession) -> dict:
    async with session.get(url, timeout=30) as resp:
        if resp.status == 200:
            return await resp.json()
        elif resp.status == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            raise ClientResponseError(resp.request_info, resp.history, status=resp.status)
        elif resp.status == 404:
            return None
        else:
            resp.raise_for_status()

@cached(ttl=CACHE_TTL)
async def get_bootstrap_static():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    async with aiohttp.ClientSession() as session:
        return await safe_request(url, session)

@cached(ttl=CACHE_TTL // 2)
async def get_entry_history(entry_id: int):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    async with aiohttp.ClientSession() as session:
        return await safe_request(url, session)

@cached(ttl=CACHE_TTL // 2)
async def get_entry_picks(entry_id: int, event: int):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{event}/picks/"
    async with aiohttp.ClientSession() as session:
        return await safe_request(url, session)

@cached(ttl=CACHE_TTL // 2)
async def get_league_standings(league_id: int):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    async with aiohttp.ClientSession() as session:
        return await safe_request(url, session)

@cached(ttl=CACHE_TTL // 2)
async def get_event_live(event: int):
    url = f"https://fantasy.premierleague.com/api/event/{event}/live/"
    async with aiohttp.ClientSession() as session:
        return await safe_request(url, session)

# Асинхронные функции для получения текущего тура, дедлайна и проверки завершённости
async def get_current_event():
    """Возвращает номер текущего тура."""
    data = await get_bootstrap_static()
    for e in data.get("events", []):
        if e.get("is_current"):
            return e["id"]
    return None

async def get_event_deadline(event: int):
    """Возвращает datetime дедлайна для указанного тура."""
    data = await get_bootstrap_static()
    for e in data.get("events", []):
        if e["id"] == event:
            return datetime.fromisoformat(e["deadline_time"].replace('Z', '+00:00'))
    return None

async def is_event_finished(event: int) -> bool:
    """Проверяет, завершён ли тур."""
    data = await get_bootstrap_static()
    for e in data.get("events", []):
        if e["id"] == event:
            return e.get("finished", False)
    return False
