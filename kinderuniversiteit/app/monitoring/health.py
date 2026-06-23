"""Health-check probes used by the /health endpoint and Docker HEALTHCHECK."""
from sqlalchemy import text

from app.core.config import settings
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.ai.rag.vector_store import get_chroma_client


async def check_database() -> bool:
    if not settings.database_url:
        return False
    try:
        from app.infrastructure.database.session import _get_engine
        eng, _ = _get_engine()
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    if not settings.redis_url:
        return False
    try:
        redis = await get_redis()
        return bool(await redis.ping())
    except Exception:
        return False


async def check_chroma() -> bool:
    try:
        import asyncio
        client = await asyncio.to_thread(get_chroma_client)
        await asyncio.to_thread(client.heartbeat)
        return True
    except Exception:
        return False
