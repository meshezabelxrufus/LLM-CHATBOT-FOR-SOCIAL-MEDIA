"""SQLAlchemy ORM model for the daily_metrics table.

Pre-computed aggregate metrics, refreshed once per day by a background job.
Avoids full-table scans of analytics_events on every dashboard load.

Granularity: one row per (tenant, date, channel).
A NULL channel row holds the cross-channel totals for that date.

The functional unique index (in the migration) handles NULL channel correctly:
  UNIQUE (COALESCE(tenant_id::text, ''), date, COALESCE(channel, ''))
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class DailyMetricsModel(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # NULL = cross-channel total row; non-NULL = per-channel breakdown.
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Counters ──────────────────────────────────────────────────────────────
    conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Conversations that were opened for the first time on this date.
    new_conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Averages ──────────────────────────────────────────────────────────────
    avg_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # When this row was last recomputed (used to detect stale rows).
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
