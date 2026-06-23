"""Async Redis client — used for rate-limiting and conversation-state caching."""
import redis.asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(str(settings.redis_url), decode_responses=True)
    return _redis
