"""SQLAlchemy 2.0 async implementation of IConversationRepository."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.conversation_repository import IConversationRepository
from app.core.logging import get_logger
from app.domain.entities.conversation import Conversation
from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState
from app.infrastructure.database.mappers import (
    conversation_from_domain,
    conversation_to_domain,
)
from app.infrastructure.database.models.conversation_model import ConversationModel

logger = get_logger(__name__)


class SQLConversationRepository(IConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Conversation | None:
        stmt = select(ConversationModel).where(ConversationModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return conversation_to_domain(model) if model else None

    async def get_by_contact(self, contact_id: str) -> Conversation | None:
        """Most recent conversation for this contact, any channel."""
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.contact_id == contact_id)
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return conversation_to_domain(model) if model else None

    async def get_active_by_contact(
        self, contact_id: str, channel: Channel
    ) -> Conversation | None:
        """Active conversation for this contact on a specific channel.
        Uses the compound index (contact_id, channel, state)."""
        stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.contact_id == contact_id,
                ConversationModel.channel == channel.value,
                ConversationModel.state == ConversationState.ACTIVE.value,
            )
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return conversation_to_domain(model) if model else None

    async def list_by_state(
        self,
        state: ConversationState,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.state == state.value)
            .order_by(ConversationModel.last_interaction_at.desc().nullslast())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [conversation_to_domain(row) for row in result.scalars().all()]

    async def save(self, conversation: Conversation) -> Conversation:
        model = conversation_from_domain(conversation)
        self._session.add(model)
        await self._session.flush()
        logger.info("conversation_saved", conversation_id=str(conversation.id))
        return conversation_to_domain(model)

    async def update(self, conversation: Conversation) -> Conversation:
        stmt = select(ConversationModel).where(ConversationModel.id == conversation.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one()

        model.state = conversation.state.value
        model.language = conversation.language
        model.last_interaction_at = conversation.last_interaction_at
        model.metadata_ = conversation.metadata
        model.updated_at = datetime.now(tz=timezone.utc)

        await self._session.flush()
        logger.info(
            "conversation_updated",
            conversation_id=str(conversation.id),
            state=conversation.state.value,
        )
        return conversation_to_domain(model)
