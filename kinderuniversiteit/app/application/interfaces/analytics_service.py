from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.value_objects.ai_response import AIResponse


class IAnalyticsService(ABC):
    @abstractmethod
    async def record_interaction(
        self,
        conversation_id: UUID,
        user_message: str,
        response: AIResponse,
        channel: str,
        response_time_ms: int | None = None,
        is_escalated: bool = False,
    ) -> None: ...

    @abstractmethod
    async def record_fallback(
        self,
        contact_id: str,
        channel: str,
        error_type: str,
        response_time_ms: int | None = None,
        conversation_id: UUID | None = None,
    ) -> None: ...
