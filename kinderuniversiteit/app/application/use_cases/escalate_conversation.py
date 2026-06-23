"""
EscalateConversation — use case for external / manual escalation triggers.

Used by:
  - Admin API endpoints (staff initiating escalation from a dashboard)
  - Scheduled jobs (auto-escalate conversations idle > N hours)
  - Webhook endpoint when the engine detects a trigger at the HTTP layer

For AI-pipeline-driven escalation during normal message handling, use
ConversationMemoryService.escalate() directly from HandleIncomingMessage.
This use case is the entry-point for callers that live outside the message
pipeline and only hold a conversation_id + reason string.
"""
from __future__ import annotations

from uuid import UUID

from app.application.services.conversation_memory_service import ConversationMemoryService
from app.core.logging import get_logger
from app.domain.entities.escalation import Escalation

logger = get_logger(__name__)


class EscalateConversation:
    def __init__(self, memory: ConversationMemoryService) -> None:
        self._memory = memory

    async def execute(
        self,
        conversation_id: UUID,
        reason: str,
    ) -> Escalation:
        """Mark the conversation as escalated and persist an Escalation record.

        Idempotent — safe to call multiple times; returns the existing open
        escalation if one already exists rather than creating a duplicate.
        """
        escalation = await self._memory.escalate(
            conversation_id=conversation_id,
            reason=reason,
        )
        logger.info(
            "manual_escalation_complete",
            conversation_id=str(conversation_id),
            escalation_id=str(escalation.id),
            reason=reason,
        )
        return escalation
