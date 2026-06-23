"""Async SQLAlchemy engine and session factory."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine = None
_AsyncSessionFactory = None


def _get_engine():
    global _engine, _AsyncSessionFactory
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured. "
                "Set the DATABASE_URL environment variable to connect to PostgreSQL."
            )
        _engine = create_async_engine(
            str(settings.database_url),
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=not settings.is_production,
            future=True,
        )
        _AsyncSessionFactory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _AsyncSessionFactory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    _, factory = _get_engine()
    async with factory() as session:
        yield session
