"""
GET /api/v1/analytics/* — internal reporting endpoints.

All endpoints require a date range via `from_date` / `to_date` query params
(ISO-8601 format: YYYY-MM-DD).

Report endpoints (daily / weekly / monthly) accept optional period params and
default to the previous complete period so a 00:05 UTC cron always gets clean
data without any arguments.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.analytics import metrics as m
from app.analytics.report_service import ReportService
from app.api.dependencies.services import get_analytics_repository
from app.application.interfaces.analytics_repository import IAnalyticsRepository
from app.domain.value_objects.analytics_report import (
    AnalyticsReport,
    FAQEntry,
    PeriodBucket,
    SummaryMetrics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Shared query-param annotation used by range endpoints.
_From = Annotated[date, Query(description="Start date inclusive (YYYY-MM-DD)")]
_To = Annotated[date, Query(description="End date inclusive (YYYY-MM-DD)")]


# ── Summary ───────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=None)
async def get_summary(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> SummaryMetrics:
    """Rolled-up totals: conversation count, escalation rate, fallback rate,
    average response time, average confidence, and per-channel breakdown."""
    return await m.summary(repo, from_date, to_date)


# ── Conversations ─────────────────────────────────────────────────────────────


@router.get("/conversations/daily", response_model=None)
async def conversations_daily(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> list[PeriodBucket]:
    """Conversation and message counts bucketed by calendar day."""
    return await m.daily_message_counts(repo, from_date, to_date)


@router.get("/conversations/weekly", response_model=None)
async def conversations_weekly(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> list[PeriodBucket]:
    """Conversation and message counts bucketed by ISO week."""
    return await m.weekly_message_counts(repo, from_date, to_date)


@router.get("/conversations/monthly", response_model=None)
async def conversations_monthly(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> list[PeriodBucket]:
    """Conversation and message counts bucketed by calendar month."""
    return await m.monthly_message_counts(repo, from_date, to_date)


# ── Escalations ───────────────────────────────────────────────────────────────


@router.get("/escalation-rate")
async def get_escalation_rate(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> dict:
    """Fraction of messages that triggered an escalation (0.0–1.0)."""
    rate = await m.escalation_rate(repo, from_date, to_date)
    return {"escalation_rate": rate, "from_date": from_date, "to_date": to_date}


# ── Fallback rate ─────────────────────────────────────────────────────────────


@router.get("/fallback-rate")
async def get_fallback_rate(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> dict:
    """Fraction of interactions where the AI pipeline failed and a canned
    fallback message was returned (0.0–1.0)."""
    rate = await m.fallback_rate(repo, from_date, to_date)
    return {"fallback_rate": rate, "from_date": from_date, "to_date": to_date}


# ── Response time ─────────────────────────────────────────────────────────────


@router.get("/response-time")
async def get_avg_response_time(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> dict:
    """Average end-to-end response time in milliseconds."""
    avg_ms = await m.avg_response_time(repo, from_date, to_date)
    return {
        "avg_response_time_ms": avg_ms,
        "from_date": from_date,
        "to_date": to_date,
    }


# ── Confidence ────────────────────────────────────────────────────────────────


@router.get("/confidence")
async def get_avg_confidence(
    from_date: _From,
    to_date: _To,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> dict:
    """Average AI confidence score (0.0–1.0) across all processed messages."""
    score = await m.avg_confidence_score(repo, from_date, to_date)
    return {
        "avg_confidence_score": score,
        "from_date": from_date,
        "to_date": to_date,
    }


# ── FAQ ───────────────────────────────────────────────────────────────────────


@router.get("/faq", response_model=None)
async def get_top_questions(
    from_date: _From,
    to_date: _To,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> list[FAQEntry]:
    """Most frequently asked questions ranked by occurrence count."""
    return await m.top_questions(repo, from_date, to_date, limit=limit)


# ── Pre-built period reports ──────────────────────────────────────────────────


@router.get("/reports/daily", response_model=None)
async def daily_report(
    for_date: Annotated[
        date | None,
        Query(description="Target date (YYYY-MM-DD). Defaults to yesterday."),
    ] = None,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> AnalyticsReport:
    """Complete daily report: summary + per-day bucket + top questions.
    Defaults to yesterday so a 00:05 UTC cron always gets the previous day."""
    svc = ReportService(repo)
    return await svc.daily_report(for_date)


@router.get("/reports/weekly", response_model=None)
async def weekly_report(
    week_start: Annotated[
        date | None,
        Query(description="Monday of the target week (YYYY-MM-DD). Defaults to last week."),
    ] = None,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> AnalyticsReport:
    """Complete weekly report: summary + per-day buckets + top questions."""
    svc = ReportService(repo)
    return await svc.weekly_report(week_start)


@router.get("/reports/monthly", response_model=None)
async def monthly_report(
    year: Annotated[int | None, Query(ge=2020, le=2099)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    repo: IAnalyticsRepository = Depends(get_analytics_repository),
) -> AnalyticsReport:
    """Complete monthly report: summary + per-week buckets + top questions.
    Pass ?year=2026&month=6 for a specific month; defaults to last month."""
    svc = ReportService(repo)
    return await svc.monthly_report(year, month)
