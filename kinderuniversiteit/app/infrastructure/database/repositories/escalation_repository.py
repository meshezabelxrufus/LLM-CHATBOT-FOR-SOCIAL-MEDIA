"""SQLAlchemy 2.0 async implementation of IEscalationRepository."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.escalation_repository import IEscalationRepository
from app.core.exceptions import ConversationNotFoundError
from app.core.logging import get_logger
from app.domain.entities.escalation import Escalation
from app.infrastructure.database.mappers import escalation_from_domain, escalation_to_domain
from app.infrastructure.database.models.escalation_model import EscalationModel

logger = get_logger(__name__)


class SQLEscalationRepository(IEscalationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Escalation | None:
        stmt = select(EscalationModel).where(EscalationModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return escalation_to_domain(model) if model else None

    async def get_open_by_conversation(
        self, conversation_id: UUID
    ) -> Escalation | None:
        """Most recent unresolved escalation for this conversation.
        Uses the compound index (conversation_id, resolved)."""
        stmt = (
            select(EscalationModel)
            .where(
                EscalationModel.conversation_id == conversation_id,
                EscalationModel.resolved.is_(False),
            )
            .order_by(EscalationModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return escalation_to_domain(model) if model else None

    async def list_unresolved(
        self, limit: int = 50, offset: int = 0
    ) -> list[Escalation]:
        stmt = (
            select(EscalationModel)
            .where(EscalationModel.resolved.is_(False))
            .order_by(EscalationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [escalation_to_domain(row) for row in result.scalars().all()]

    async def save(self, escalation: Escalation) -> Escalation:
        model = escalation_from_domain(escalation)
        self._session.add(model)
        await self._session.flush()
        logger.info(
            "escalation_saved",
            escalation_id=str(escalation.id),
            conversation_id=str(escalation.conversation_id),
            reason=escalation.reason,
        )
        return escalation_to_domain(model)

    async def resolve(
        self,
        escalation_id: UUID,
        agent_id: str,
        notes: str = "",
    ) -> Escalation:
        stmt = select(EscalationModel).where(EscalationModel.id == escalation_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise ConversationNotFoundError(f"Escalation {escalation_id} not found")

        model.resolved = True
        model.agent_id = agent_id
        model.notes = notes
        model.resolved_at = datetime.now(tz=timezone.utc)

        await self._session.flush()
        logger.info(
            "escalation_resolved",
            escalation_id=str(escalation_id),
            agent_id=agent_id,
        )
        return escalation_to_domain(model)
