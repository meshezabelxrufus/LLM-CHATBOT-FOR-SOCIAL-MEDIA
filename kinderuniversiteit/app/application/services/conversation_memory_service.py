"""
Conversation memory service.

Single entry-point for all conversation-state operations. Use cases call this
service; they never talk to repositories directly. The service manages:

  - Contact upsert (keep ManyChat subscriber data fresh)
  - Conversation session lifecycle (get-or-create, close, re-open)
  - Message persistence and history retrieval
  - Language tracking per conversation
  - Escalation creation and resolution
  - History formatting for the OpenAI Responses API
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.application.interfaces.contact_repository import IContactRepository
from app.application.interfaces.conversation_repository import IConversationRepository
from app.application.interfaces.escalation_repository import IEscalationRepository
from app.application.interfaces.message_repository import IMessageRepository
from app.core.exceptions import ConversationNotFoundError, EscalationError
from app.core.logging import get_logger
from app.domain.entities.contact import Contact
from app.domain.entities.conversation import Conversation
from app.domain.entities.escalation import Escalation
from app.domain.entities.message import Message
from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState
from app.domain.enums.message_role import MessageRole

logger = get_logger(__name__)

# How many recent messages to load as the AI context window by default.
DEFAULT_HISTORY_WINDOW = 10


class ConversationMemoryService:
    def __init__(
        self,
        conversation_repo: IConversationRepository,
        message_repo: IMessageRepository,
        contact_repo: IContactRepository,
        escalation_repo: IEscalationRepository,
    ) -> None:
        self._conversations = conversation_repo
        self._messages = message_repo
        self._contacts = contact_repo
        self._escalations = escalation_repo

    # ── Contact ───────────────────────────────────────────────────────────────

    async def touch_contact(
        self,
        external_id: str,
        channel: Channel,
        display_name: str = "",
        locale: str = "nl",
    ) -> Contact:
        """Upsert the contact record, refreshing last_seen_at and display name."""
        contact = Contact(
            external_id=external_id,
            channel=channel,
            display_name=display_name,
            locale=locale,
            last_seen_at=datetime.now(tz=timezone.utc),
        )
        return await self._contacts.upsert(contact)

    # ── Conversation session ──────────────────────────────────────────────────

    async def get_or_create_conversation(
        self,
        contact_id: str,
        channel: Channel,
        language: str = "nl",
    ) -> Conversation:
        """Return the open conversation for this contact+channel, or open a new one.

        A new conversation is created when:
        - No conversation exists yet for this contact on this channel.
        - The existing conversation has been closed or escalated and resolved.
        """
        existing = await self._conversations.get_active_by_contact(contact_id, channel)
        if existing:
            logger.info(
                "conversation_resumed",
                conversation_id=str(existing.id),
                contact_id=contact_id,
                channel=channel.value,
            )
            return existing

        conversation = Conversation(
            contact_id=contact_id,
            channel=channel,
            language=language,
            last_interaction_at=datetime.now(tz=timezone.utc),
        )
        created = await self._conversations.save(conversation)
        logger.info(
            "conversation_created",
            conversation_id=str(created.id),
            contact_id=contact_id,
            channel=channel.value,
            language=language,
        )
        return created

    async def close_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self._require_conversation(conversation_id)
        conversation.state = ConversationState.CLOSED
        conversation.updated_at = datetime.now(tz=timezone.utc)
        return await self._conversations.update(conversation)

    # ── Message persistence ───────────────────────────────────────────────────

    async def save_turn(
        self,
        conversation_id: UUID,
        user_text: str,
        assistant_text: str,
        tokens_used: int = 0,
        confidence_score: float | None = None,
    ) -> tuple[Message, Message]:
        """Persist the user message and assistant reply as one logical turn.

        Also updates last_interaction_at on the conversation so session-timeout
        logic can work off a single indexed column.
        """
        conversation = await self._require_conversation(conversation_id)

        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_text,
        )
        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=assistant_text,
            tokens_used=tokens_used,
            confidence_score=confidence_score,
        )

        saved_user = await self._messages.save(user_msg)
        saved_assistant = await self._messages.save(assistant_msg)

        # Advance the interaction timestamp without changing any other state.
        conversation.last_interaction_at = datetime.now(tz=timezone.utc)
        await self._conversations.update(conversation)

        return saved_user, saved_assistant

    # ── History retrieval ─────────────────────────────────────────────────────

    async def load_history(
        self,
        conversation_id: UUID,
        limit: int = DEFAULT_HISTORY_WINDOW,
    ) -> list[Message]:
        """Return the most recent `limit` messages, oldest first.
        This is the context window passed to the AI on every turn."""
        return await self._messages.get_latest(conversation_id, n=limit)

    def format_for_prompt(self, messages: list[Message]) -> list[dict]:
        """Convert domain Message entities to the OpenAI Responses API input format.

        Returns [{"role": "user"|"assistant", "content": "..."}] ready to be
        passed as the `input` parameter of client.responses.create().
        """
        return [{"role": msg.role.value, "content": msg.content} for msg in messages]

    async def load_history_for_prompt(
        self,
        conversation_id: UUID,
        limit: int = DEFAULT_HISTORY_WINDOW,
    ) -> list[dict]:
        """Convenience: load and format in one call."""
        messages = await self.load_history(conversation_id, limit=limit)
        return self.format_for_prompt(messages)

    # ── Language ──────────────────────────────────────────────────────────────

    async def update_language(
        self, conversation_id: UUID, language: str
    ) -> Conversation:
        """Set the detected language on the conversation.

        Call this after the first user message when language detection runs.
        Subsequent messages use the stored value; do not re-detect every turn.
        """
        conversation = await self._require_conversation(conversation_id)
        if conversation.language == language:
            return conversation
        conversation.language = language
        updated = await self._conversations.update(conversation)
        logger.info(
            "language_updated",
            conversation_id=str(conversation_id),
            language=language,
        )
        return updated

    # ── Escalation ────────────────────────────────────────────────────────────

    async def escalate(
        self,
        conversation_id: UUID,
        reason: str,
    ) -> Escalation:
        """Mark the conversation as escalated and open an Escalation record.

        Idempotent: if an unresolved escalation already exists, returns it
        without creating a duplicate.
        """
        conversation = await self._require_conversation(conversation_id)

        existing = await self._escalations.get_open_by_conversation(conversation_id)
        if existing:
            logger.info(
                "escalation_already_open",
                conversation_id=str(conversation_id),
                escalation_id=str(existing.id),
            )
            return existing

        escalation = Escalation(
            conversation_id=conversation_id,
            reason=reason,
        )
        saved_escalation = await self._escalations.save(escalation)

        conversation.state = ConversationState.ESCALATED
        await self._conversations.update(conversation)

        logger.info(
            "conversation_escalated",
            conversation_id=str(conversation_id),
            reason=reason,
        )
        return saved_escalation

    async def resolve_escalation(
        self,
        conversation_id: UUID,
        agent_id: str,
        notes: str = "",
    ) -> Escalation:
        """Resolve the open escalation and reactivate the conversation."""
        open_escalation = await self._escalations.get_open_by_conversation(
            conversation_id
        )
        if not open_escalation:
            raise EscalationError(
                f"No open escalation found for conversation {conversation_id}"
            )

        resolved = await self._escalations.resolve(
            open_escalation.id, agent_id=agent_id, notes=notes
        )

        conversation = await self._require_conversation(conversation_id)
        conversation.state = ConversationState.ACTIVE
        await self._conversations.update(conversation)

        logger.info(
            "escalation_resolved",
            conversation_id=str(conversation_id),
            agent_id=agent_id,
        )
        return resolved

    # ── Private ───────────────────────────────────────────────────────────────

    async def _require_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} not found"
            )
        return conversation
