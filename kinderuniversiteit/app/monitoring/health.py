"""Health-check probes used by the /health endpoint and Docker HEALTHCHECK."""
from sqlalchemy import text

from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database.session import engine
from app.infrastructure.ai.rag.vector_store import get_chroma_client


async def check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
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
