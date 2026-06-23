"""
HandleIncomingMessage — the central use case.

Orchestrates the full lifecycle of a single inbound message:

  1.  Upsert contact record (keep ManyChat subscriber data current)
  2.  Get or create an active conversation for this contact + channel
  3.  Update detected language on first turn
  4.  Pre-AI escalation check (payment status / financial request keywords)
       → if hold_reply: skip AI, persist holding turn, escalate, return
  5.  Load recent history as the AI context window
  6.  Call the AI pipeline (RAG + OpenAI Responses API)
  7.  Strip machine-readable [ESCALATE] block from AI text
  8.  Persist user message + assistant reply as one atomic turn
  9.  Post-AI escalation detection ([ESCALATE] block / confidence / flag)
  10. Record an analytics event (failure does not block the reply)
  11. Return the clean reply text to the calling adapter
"""
from __future__ import annotations

import time

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.analytics_service import IAnalyticsService
from app.application.services.conversation_memory_service import ConversationMemoryService
from app.application.services.escalation_engine import EscalationRuleEngine
from app.core.logging import get_logger
from app.domain.value_objects.escalation_decision import EscalationDecision
from app.domain.value_objects.incoming_message import IncomingMessage

logger = get_logger(__name__)

HISTORY_WINDOW = 10


class HandleIncomingMessage:
    def __init__(
        self,
        memory: ConversationMemoryService,
        ai_service: IAIService,
        analytics_service: IAnalyticsService,
        escalation_engine: EscalationRuleEngine | None = None,
    ) -> None:
        self._memory = memory
        self._ai = ai_service
        self._analytics = analytics_service
        self._escalation_engine = escalation_engine or EscalationRuleEngine()

    async def execute(self, incoming: IncomingMessage) -> str:
        log = logger.bind(
            contact_id=incoming.contact_id,
            channel=incoming.channel.value,
        )
        log.info("handle_incoming_message_start", text_len=len(incoming.text))
        _started_at = time.monotonic()

        # 1. Keep the contact record fresh.
        await self._memory.touch_contact(
            external_id=incoming.contact_id,
            channel=incoming.channel,
            display_name=incoming.display_name,
            locale=incoming.locale,
        )

        # 2. Resolve or open a conversation session.
        conversation = await self._memory.get_or_create_conversation(
            contact_id=incoming.contact_id,
            channel=incoming.channel,
            language=incoming.language,
        )
        log = log.bind(conversation_id=str(conversation.id))

        # 3. Persist detected language on the first turn only.
        if conversation.language != incoming.language:
            await self._memory.update_language(conversation.id, incoming.language)

        # 4. Pre-AI escalation check ─────────────────────────────────────────
        pre_decision = self._escalation_engine.detect_from_message(
            incoming.text, incoming.language
        )

        if pre_decision.should_escalate and pre_decision.hold_reply:
            # Payment-status rule: mandatory holding reply, skip the AI.
            reply_text = pre_decision.human_message
            await self._memory.save_turn(
                conversation_id=conversation.id,
                user_text=incoming.text,
                assistant_text=reply_text,
                tokens_used=0,
                confidence_score=0.0,
            )
            await self._memory.escalate(
                conversation_id=conversation.id,
                reason=pre_decision.reason,
            )
            log.info(
                "pre_ai_escalation_hold",
                trigger=pre_decision.trigger.value if pre_decision.trigger else "unknown",
                urgency=pre_decision.urgency,
            )
            return reply_text

        # 5. Load the context window for the AI prompt.
        history = await self._memory.load_history_for_prompt(
            conversation.id, limit=HISTORY_WINDOW
        )

        # 6. Generate AI response (RAG retrieval + OpenAI Responses API).
        ai_response = await self._ai.generate_response(
            conversation_id=conversation.id,
            user_message=incoming.text,
            history=history,
        )
        log.info(
            "ai_response_generated",
            tokens=ai_response.tokens_used,
            confidence=ai_response.confidence_score,
            requires_escalation=ai_response.requires_escalation,
        )

        # 7. Strip the machine-readable [ESCALATE] block before persisting and
        #    returning.  The block is for internal routing only — the user sees
        #    only the human-readable portion of the AI reply.
        clean_text = self._escalation_engine.strip_escalate_block(ai_response.text)

        # 8. Persist the turn — both messages in the same DB transaction.
        await self._memory.save_turn(
            conversation_id=conversation.id,
            user_text=incoming.text,
            assistant_text=clean_text,
            tokens_used=ai_response.tokens_used,
            confidence_score=ai_response.confidence_score,
        )

        # 9. Post-AI escalation detection ────────────────────────────────────
        #    Prefer the post-AI decision (has structured block data); fall back
        #    to the pre-AI financial-request match if no post-AI signal fires.
        post_decision = self._escalation_engine.detect_from_ai_response(ai_response)

        winning_decision: EscalationDecision | None = None
        if post_decision.should_escalate:
            winning_decision = post_decision
        elif pre_decision.should_escalate and not pre_decision.hold_reply:
            # Financial-request pre-AI match — AI already responded; now escalate.
            winning_decision = pre_decision

        if winning_decision is not None:
            await self._memory.escalate(
                conversation_id=conversation.id,
                reason=winning_decision.reason,
            )
            log.info(
                "conversation_escalated",
                trigger=winning_decision.trigger.value if winning_decision.trigger else "unknown",
                urgency=winning_decision.urgency,
                confidence=ai_response.confidence_score,
            )

        # 10. Record analytics (fire-and-forget; failure does not block reply).
        response_time_ms = int((time.monotonic() - _started_at) * 1000)
        try:
            await self._analytics.record_interaction(
                conversation_id=conversation.id,
                user_message=incoming.text,
                response=ai_response,
                channel=incoming.channel.value,
                response_time_ms=response_time_ms,
                is_escalated=winning_decision is not None,
            )
        except Exception as exc:
            log.warning("analytics_record_failed", error=str(exc))

        log.info("handle_incoming_message_complete")
        return clean_text
