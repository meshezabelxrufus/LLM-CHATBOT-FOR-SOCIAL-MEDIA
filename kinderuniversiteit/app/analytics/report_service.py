"""
ReportService — generates daily, weekly, and monthly analytics reports.

Each report contains:
  - A rolled-up SummaryMetrics for the whole period
  - One PeriodBucket per time bucket within the period
  - Top-20 FAQ entries for the period

All date-range defaults follow the convention of reporting on the *previous*
complete period (yesterday, last week, last month) so a scheduled cron at
00:05 UTC always produces a clean report.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.application.interfaces.analytics_repository import IAnalyticsRepository
from app.analytics.metrics import _day_range
from app.core.logging import get_logger
from app.domain.value_objects.analytics_report import AnalyticsReport

logger = get_logger(__name__)

_FAQ_LIMIT = 20


class ReportService:
    def __init__(self, repo: IAnalyticsRepository) -> None:
        self._repo = repo

    # ── Public API ────────────────────────────────────────────────────────────

    async def daily_report(self, for_date: date | None = None) -> AnalyticsReport:
        """Report for a single calendar day.  Defaults to yesterday."""
        target = for_date or _yesterday()
        start, end = _day_range(target, target)
        return await self._build("daily", target, target, start, end)

    async def weekly_report(self, week_start: date | None = None) -> AnalyticsReport:
        """Report for a Monday–Sunday week.  Defaults to last week."""
        monday = week_start or _last_monday()
        sunday = monday + timedelta(days=6)
        start, end = _day_range(monday, sunday)
        return await self._build("weekly", monday, sunday, start, end)

    async def monthly_report(
        self, year: int | None = None, month: int | None = None
    ) -> AnalyticsReport:
        """Report for a full calendar month.  Defaults to last month."""
        today = date.today()
        if year is None or month is None:
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            year = last_month_end.year
            month = last_month_end.month
        from_date = date(year, month, 1)
        to_date = _last_day_of_month(year, month)
        start, end = _day_range(from_date, to_date)
        return await self._build("monthly", from_date, to_date, start, end)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _build(
        self,
        report_type: str,
        period_start: date,
        period_end: date,
        start: datetime,
        end: datetime,
    ) -> AnalyticsReport:
        granularity = {"daily": "day", "weekly": "day", "monthly": "week"}[report_type]

        summary, buckets, faq = (
            await self._repo.get_summary(start, end),
            await self._repo.get_period_buckets(start, end, granularity=granularity),  # type: ignore[arg-type]
            await self._repo.get_top_questions(start, end, limit=_FAQ_LIMIT),
        )

        report = AnalyticsReport(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(tz=timezone.utc),
            summary=summary,
            buckets=buckets,
            top_questions=faq,
        )
        logger.info(
            "report_generated",
            type=report_type,
            period_start=str(period_start),
            period_end=str(period_end),
            conversations=summary.conversation_count,
            messages=summary.message_count,
        )
        return report


# ── Date helpers ──────────────────────────────────────────────────────────────


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _last_monday() -> date:
    today = date.today()
    # today.weekday(): Monday=0 … Sunday=6
    # Go back to last Monday (7 days before this Monday)
    days_since_monday = today.weekday()
    this_monday = today - timedelta(days=days_since_monday)
    return this_monday - timedelta(weeks=1)


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)
