"""
SQLAlchemy 2.0 async implementation of IAnalyticsRepository.

All heavy aggregation is done in PostgreSQL.  Raw SQL (via text()) is used for
queries that involve JSON path operators (->>) which are cleaner to write as
SQL strings than through the SQLAlchemy expression layer.

Query tuning notes:
  - ix_analytics_events_created_event_type  covers time-range + event_type filters
  - ix_analytics_events_created_channel     covers channel-breakdown queries
  - DATE_TRUNC granularity is passed as a bind parameter; Postgres optimises it.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.analytics_repository import IAnalyticsRepository
from app.domain.value_objects.analytics_report import FAQEntry, PeriodBucket, SummaryMetrics
from app.infrastructure.database.models.analytics_event_model import AnalyticsEventModel

# Event types written by DBAnalyticsService.
_EV_MESSAGE = "message_processed"
_EV_FALLBACK = "fallback_sent"
_ALL_EVENTS = (_EV_MESSAGE, _EV_FALLBACK)


class SQLAnalyticsRepository(IAnalyticsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Summary ───────────────────────────────────────────────────────────────

    async def get_summary(self, start: datetime, end: datetime) -> SummaryMetrics:
        """Return rolled-up totals for the given date range."""
        m = AnalyticsEventModel

        row = (
            await self._session.execute(
                select(
                    func.count(func.distinct(m.conversation_id)).label("conversations"),
                    func.count().label("messages"),
                    func.count().filter(m.escalated.is_(True)).label("escalations"),
                    func.count().filter(m.is_fallback.is_(True)).label("fallbacks"),
                    func.avg(m.response_time_ms).label("avg_rt"),
                    func.avg(m.confidence_score).label("avg_conf"),
                ).where(
                    m.created_at >= start,
                    m.created_at < end,
                    m.event_type.in_(_ALL_EVENTS),
                )
            )
        ).one()

        channel_breakdown = await self.get_channel_breakdown(start, end)

        return SummaryMetrics(
            period_start=start.date(),
            period_end=end.date(),
            conversation_count=row.conversations or 0,
            message_count=row.messages or 0,
            escalation_count=row.escalations or 0,
            fallback_count=row.fallbacks or 0,
            avg_response_time_ms=float(row.avg_rt) if row.avg_rt is not None else None,
            avg_confidence_score=float(row.avg_conf) if row.avg_conf is not None else None,
            by_channel=channel_breakdown,
        )

    # ── Period buckets ────────────────────────────────────────────────────────

    async def get_period_buckets(
        self,
        start: datetime,
        end: datetime,
        granularity: Literal["day", "week", "month"],
    ) -> list[PeriodBucket]:
        """Return one PeriodBucket per time bucket within [start, end)."""
        m = AnalyticsEventModel
        bucket_col = func.date_trunc(granularity, m.created_at).label("period")

        rows = (
            await self._session.execute(
                select(
                    bucket_col,
                    func.count(func.distinct(m.conversation_id)).label("conversations"),
                    func.count().label("messages"),
                    func.count().filter(m.escalated.is_(True)).label("escalations"),
                    func.count().filter(m.is_fallback.is_(True)).label("fallbacks"),
                    func.avg(m.response_time_ms).label("avg_rt"),
                    func.avg(m.confidence_score).label("avg_conf"),
                ).where(
                    m.created_at >= start,
                    m.created_at < end,
                    m.event_type.in_(_ALL_EVENTS),
                )
                .group_by(bucket_col)
                .order_by(bucket_col)
            )
        ).all()

        return [
            PeriodBucket(
                period_start=r.period.date() if hasattr(r.period, "date") else date.fromisoformat(str(r.period)[:10]),
                conversation_count=r.conversations or 0,
                message_count=r.messages or 0,
                escalation_count=r.escalations or 0,
                fallback_count=r.fallbacks or 0,
                avg_response_time_ms=float(r.avg_rt) if r.avg_rt is not None else None,
                avg_confidence_score=float(r.avg_conf) if r.avg_conf is not None else None,
            )
            for r in rows
        ]

    # ── FAQ ───────────────────────────────────────────────────────────────────

    async def get_top_questions(
        self,
        start: datetime,
        end: datetime,
        limit: int = 20,
    ) -> list[FAQEntry]:
        """Return the most frequently asked questions in the period."""
        raw = await self._session.execute(
            text(
                """
                SELECT
                    payload->>'question_text'  AS question,
                    COUNT(*)                   AS cnt
                FROM analytics_events
                WHERE created_at  >= :start
                  AND created_at  <  :end
                  AND event_type   = :ev_type
                  AND is_fallback  = false
                  AND payload->>'question_text' IS NOT NULL
                  AND payload->>'question_text' <> ''
                GROUP BY payload->>'question_text'
                ORDER BY cnt DESC
                LIMIT :lim
                """
            ),
            {"start": start, "end": end, "ev_type": _EV_MESSAGE, "lim": limit},
        )
        rows = raw.all()
        if not rows:
            return []

        total = sum(r.cnt for r in rows)
        return [
            FAQEntry(
                question=r.question,
                count=r.cnt,
                percentage=round(r.cnt / total * 100, 1) if total else 0.0,
            )
            for r in rows
        ]

    # ── Channel breakdown ─────────────────────────────────────────────────────

    async def get_channel_breakdown(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[str, int]:
        """Return message count per channel."""
        m = AnalyticsEventModel
        rows = (
            await self._session.execute(
                select(m.channel, func.count().label("cnt"))
                .where(
                    m.created_at >= start,
                    m.created_at < end,
                    m.event_type.in_(_ALL_EVENTS),
                )
                .group_by(m.channel)
                .order_by(func.count().desc())
            )
        ).all()
        return {r.channel: r.cnt for r in rows}
