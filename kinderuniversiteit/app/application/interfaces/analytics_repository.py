"""Abstract repository for analytics read queries."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from app.domain.value_objects.analytics_report import FAQEntry, PeriodBucket, SummaryMetrics


class IAnalyticsRepository(ABC):
    @abstractmethod
    async def get_summary(
        self,
        start: datetime,
        end: datetime,
    ) -> SummaryMetrics: ...

    @abstractmethod
    async def get_period_buckets(
        self,
        start: datetime,
        end: datetime,
        granularity: Literal["day", "week", "month"],
    ) -> list[PeriodBucket]: ...

    @abstractmethod
    async def get_top_questions(
        self,
        start: datetime,
        end: datetime,
        limit: int = 20,
    ) -> list[FAQEntry]: ...

    @abstractmethod
    async def get_channel_breakdown(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[str, int]: ...
