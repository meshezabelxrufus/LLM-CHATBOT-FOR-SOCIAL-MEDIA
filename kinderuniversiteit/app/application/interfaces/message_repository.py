"""Abstract message repository — application layer depends on this port."""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.message import Message


class IMessageRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Message | None: ...

    @abstractmethod
    async def list_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """All messages for a conversation, oldest first."""
        ...

    @abstractmethod
    async def get_latest(self, conversation_id: UUID, n: int = 10) -> list[Message]:
        """The n most recent messages, returned in chronological order (oldest first).
        Used to build the AI context window without loading the full history."""
        ...

    @abstractmethod
    async def count_by_conversation(self, conversation_id: UUID) -> int: ...

    @abstractmethod
    async def save(self, message: Message) -> Message: ...
