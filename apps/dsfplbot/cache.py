import asyncio
import time
from functools import wraps

class TTLCache:
    def __init__(self, ttl=300):
        self._cache = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def get(self, key):
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self._cache[key]
        return None

    async def set(self, key, value):
        async with self._lock:
            self._cache[key] = (value, time.time() + self._ttl)

_cache = TTLCache()

def cached(ttl=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            cached_value = await _cache.get(key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            await _cache.set(key, result)
            return result
        return wrapper
    return decorator
