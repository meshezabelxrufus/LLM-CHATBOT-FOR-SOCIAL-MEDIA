"""SQLAlchemy ORM model for the analytics_events table."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AnalyticsEventModel(Base):
    __tablename__ = "analytics_events"

    # Compound indexes that cover the two most common access patterns:
    #   - Time-range scans filtered by event_type  (report generation)
    #   - Time-range scans filtered by channel     (per-channel reports)
    __table_args__ = (
        Index("ix_analytics_events_created_event_type", "created_at", "event_type"),
        Index("ix_analytics_events_created_channel", "created_at", "channel"),
        Index("ix_analytics_events_tenant_created_at", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Nullable: fallback events fired before a conversation is created have no ID.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Wall-clock time from first byte received to response returned, in ms.
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Arbitrary JSON: question_text, sources, contact_id, error_type, etc.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
