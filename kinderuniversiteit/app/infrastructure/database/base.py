"""Declarative base shared by all ORM models — imported by Alembic env.py."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so SQLAlchemy can resolve cross-table ForeignKey
# references at mapper configuration time, regardless of import order elsewhere.
def _register_models() -> None:
    from app.infrastructure.database.models import (  # noqa: F401
        analytics_event_model,
        api_log_model,
        audit_log_model,
        contact_model,
        conversation_model,
        daily_metrics_model,
        escalation_model,
        knowledge_chunk_model,
        knowledge_document_model,
        message_model,
        tenant_model,
        user_model,
    )


_register_models()
