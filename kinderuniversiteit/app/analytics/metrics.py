"""
Metrics helpers — thin wrappers around IAnalyticsRepository.

Called by the analytics API endpoints.  All date arithmetic converts naive
`date` arguments to UTC-aware `datetime` boundaries before passing to the
repository so every query uses the same tz-aware indexed column.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.application.interfaces.analytics_repository import IAnalyticsRepository
from app.domain.value_objects.analytics_report import FAQEntry, PeriodBucket, SummaryMetrics


def _day_range(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """Convert a [from_date, to_date] inclusive range to [start, end) UTC datetimes."""
    tz = timezone.utc
    start = datetime.combine(from_date, time.min, tzinfo=tz)
    end = datetime.combine(to_date, time.max, tzinfo=tz)
    return start, end


async def daily_message_counts(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> list[PeriodBucket]:
    start, end = _day_range(from_date, to_date)
    return await repo.get_period_buckets(start, end, granularity="day")


async def weekly_message_counts(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> list[PeriodBucket]:
    start, end = _day_range(from_date, to_date)
    return await repo.get_period_buckets(start, end, granularity="week")


async def monthly_message_counts(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> list[PeriodBucket]:
    start, end = _day_range(from_date, to_date)
    return await repo.get_period_buckets(start, end, granularity="month")


async def escalation_rate(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> float:
    start, end = _day_range(from_date, to_date)
    summary = await repo.get_summary(start, end)
    return summary.escalation_rate


async def fallback_rate(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> float:
    start, end = _day_range(from_date, to_date)
    summary = await repo.get_summary(start, end)
    return summary.fallback_rate


async def avg_confidence_score(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> float | None:
    start, end = _day_range(from_date, to_date)
    summary = await repo.get_summary(start, end)
    return summary.avg_confidence_score


async def avg_response_time(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> float | None:
    start, end = _day_range(from_date, to_date)
    summary = await repo.get_summary(start, end)
    return summary.avg_response_time_ms


async def top_questions(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
    limit: int = 20,
) -> list[FAQEntry]:
    start, end = _day_range(from_date, to_date)
    return await repo.get_top_questions(start, end, limit=limit)


async def summary(
    repo: IAnalyticsRepository,
    from_date: date,
    to_date: date,
) -> SummaryMetrics:
    start, end = _day_range(from_date, to_date)
    return await repo.get_summary(start, end)
