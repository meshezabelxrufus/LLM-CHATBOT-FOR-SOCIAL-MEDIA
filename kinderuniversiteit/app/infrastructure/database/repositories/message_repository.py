"""SQLAlchemy 2.0 async implementation of IMessageRepository."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.message_repository import IMessageRepository
from app.core.logging import get_logger
from app.domain.entities.message import Message
from app.infrastructure.database.mappers import message_from_domain, message_to_domain
from app.infrastructure.database.models.message_model import MessageModel

logger = get_logger(__name__)


class SQLMessageRepository(IMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Message | None:
        stmt = select(MessageModel).where(MessageModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return message_to_domain(model) if model else None

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """All messages oldest-first — used for full history export."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [message_to_domain(row) for row in result.scalars().all()]

    async def get_latest(self, conversation_id: UUID, n: int = 10) -> list[Message]:
        """The n most recent messages in chronological order.

        Uses a subquery so the final result is oldest-first even though we
        select newest-first to get the right tail of the history.
        """
        subq = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.desc())
            .limit(n)
            .subquery()
        )
        stmt = (
            select(MessageModel)
            .join(subq, MessageModel.id == subq.c.id)
            .order_by(MessageModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [message_to_domain(row) for row in result.scalars().all()]

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        stmt = select(func.count()).where(
            MessageModel.conversation_id == conversation_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, message: Message) -> Message:
        model = message_from_domain(message)
        self._session.add(model)
        await self._session.flush()
        logger.info(
            "message_saved",
            message_id=str(message.id),
            conversation_id=str(message.conversation_id),
            role=message.role.value,
        )
        return message_to_domain(model)
