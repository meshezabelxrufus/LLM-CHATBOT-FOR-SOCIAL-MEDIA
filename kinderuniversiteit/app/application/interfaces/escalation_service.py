from abc import ABC, abstractmethod
from uuid import UUID


class IEscalationService(ABC):
    @abstractmethod
    async def escalate(self, conversation_id: UUID, reason: str) -> None: ...
