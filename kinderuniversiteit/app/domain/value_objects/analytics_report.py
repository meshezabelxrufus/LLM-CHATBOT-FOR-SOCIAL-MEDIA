"""Value objects returned by the analytics reporting layer.

All fields are immutable.  The API serialises these directly to JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class PeriodBucket:
    """Aggregated metrics for one time bucket (day / week / month)."""

    period_start: date
    conversation_count: int
    message_count: int
    escalation_count: int
    fallback_count: int
    avg_response_time_ms: float | None
    avg_confidence_score: float | None

    @property
    def escalation_rate(self) -> float:
        if self.message_count == 0:
            return 0.0
        return round(self.escalation_count / self.message_count, 4)

    @property
    def fallback_rate(self) -> float:
        if self.message_count == 0:
            return 0.0
        return round(self.fallback_count / self.message_count, 4)


@dataclass(frozen=True)
class SummaryMetrics:
    """Rolled-up totals for an arbitrary date range."""

    period_start: date
    period_end: date
    conversation_count: int
    message_count: int
    escalation_count: int
    fallback_count: int
    avg_response_time_ms: float | None
    avg_confidence_score: float | None
    by_channel: dict[str, int] = field(default_factory=dict)

    @property
    def escalation_rate(self) -> float:
        if self.message_count == 0:
            return 0.0
        return round(self.escalation_count / self.message_count, 4)

    @property
    def fallback_rate(self) -> float:
        if self.message_count == 0:
            return 0.0
        return round(self.fallback_count / self.message_count, 4)


@dataclass(frozen=True)
class FAQEntry:
    """One entry in the top-questions list."""

    question: str
    count: int
    percentage: float


@dataclass(frozen=True)
class AnalyticsReport:
    """Complete report for one period type."""

    report_type: str            # "daily" | "weekly" | "monthly"
    period_start: date
    period_end: date
    generated_at: datetime
    summary: SummaryMetrics
    buckets: list[PeriodBucket]
    top_questions: list[FAQEntry]
