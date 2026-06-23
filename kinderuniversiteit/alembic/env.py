"""Alembic async migration environment."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.infrastructure.database.base import Base

# Side-effect imports: register every model with Base.metadata so Alembic
# can detect added/removed tables during autogenerate.
from app.infrastructure.database.models import analytics_event_model  # noqa: F401
from app.infrastructure.database.models import api_log_model  # noqa: F401
from app.infrastructure.database.models import audit_log_model  # noqa: F401
from app.infrastructure.database.models import contact_model  # noqa: F401
from app.infrastructure.database.models import conversation_model  # noqa: F401
from app.infrastructure.database.models import daily_metrics_model  # noqa: F401
from app.infrastructure.database.models import escalation_model  # noqa: F401
from app.infrastructure.database.models import knowledge_chunk_model  # noqa: F401
from app.infrastructure.database.models import knowledge_document_model  # noqa: F401
from app.infrastructure.database.models import message_model  # noqa: F401
from app.infrastructure.database.models import tenant_model  # noqa: F401
from app.infrastructure.database.models import user_model  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(str(settings.database_url))
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
