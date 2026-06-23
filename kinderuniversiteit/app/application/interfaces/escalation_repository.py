"""Abstract escalation repository — application layer depends on this port."""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.escalation import Escalation


class IEscalationRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Escalation | None: ...

    @abstractmethod
    async def get_open_by_conversation(
        self, conversation_id: UUID
    ) -> Escalation | None:
        """Return the most recent unresolved escalation for this conversation."""
        ...

    @abstractmethod
    async def list_unresolved(
        self, limit: int = 50, offset: int = 0
    ) -> list[Escalation]:
        """All open escalations across all conversations, newest first."""
        ...

    @abstractmethod
    async def save(self, escalation: Escalation) -> Escalation: ...

    @abstractmethod
    async def resolve(
        self,
        escalation_id: UUID,
        agent_id: str,
        notes: str = "",
    ) -> Escalation: ...
