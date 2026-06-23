"""
DBAnalyticsService — writes analytics events to PostgreSQL.

One event is written per inbound message (event_type="message_processed").
Fallback events fired when the AI pipeline fails use event_type="fallback_sent".

The `question_text` stored in the payload JSON is normalised (lowercased,
stripped, truncated to 200 chars) so the FAQ aggregation query can GROUP BY it
without case or whitespace noise.
"""
from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.analytics_service import IAnalyticsService
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.value_objects.ai_response import AIResponse
from app.infrastructure.database.models.analytics_event_model import AnalyticsEventModel

logger = get_logger(__name__)

_EV_MESSAGE = "message_processed"
_EV_FALLBACK = "fallback_sent"


class DBAnalyticsService(IAnalyticsService):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_interaction(
        self,
        conversation_id: UUID,
        user_message: str,
        response: AIResponse,
        channel: str,
        response_time_ms: int | None = None,
        is_escalated: bool = False,
    ) -> None:
        if not settings.analytics_enabled:
            return

        event = AnalyticsEventModel(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            channel=channel,
            event_type=_EV_MESSAGE,
            tokens_used=response.tokens_used,
            confidence_score=response.confidence_score,
            escalated=is_escalated or response.requires_escalation,
            is_fallback=False,
            response_time_ms=response_time_ms,
            payload={
                "question_text": _normalise(user_message),
                "sources": response.sources,
                "requires_escalation": response.requires_escalation,
            },
        )
        self._session.add(event)
        await self._session.flush()
        logger.debug(
            "analytics_interaction_recorded",
            conversation_id=str(conversation_id),
            channel=channel,
            tokens=response.tokens_used,
            response_time_ms=response_time_ms,
        )

    async def record_fallback(
        self,
        contact_id: str,
        channel: str,
        error_type: str,
        response_time_ms: int | None = None,
        conversation_id: UUID | None = None,
    ) -> None:
        if not settings.analytics_enabled:
            return

        event = AnalyticsEventModel(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            channel=channel,
            event_type=_EV_FALLBACK,
            tokens_used=0,
            confidence_score=None,
            escalated=False,
            is_fallback=True,
            response_time_ms=response_time_ms,
            payload={
                "contact_id": contact_id,
                "error_type": error_type,
            },
        )
        self._session.add(event)
        await self._session.flush()
        logger.debug(
            "analytics_fallback_recorded",
            contact_id=contact_id,
            channel=channel,
            error_type=error_type,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise(text: str, max_len: int = 200) -> str:
    """Lowercase + strip + truncate so FAQ GROUP BY works cleanly."""
    return text.lower().strip()[:max_len]
