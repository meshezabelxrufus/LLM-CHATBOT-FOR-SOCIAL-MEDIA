"""Abstract conversation repository — application layer depends on this port."""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.conversation import Conversation
from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState


class IConversationRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Conversation | None: ...

    @abstractmethod
    async def get_by_contact(self, contact_id: str) -> Conversation | None:
        """Most recent conversation for this contact regardless of channel."""
        ...

    @abstractmethod
    async def get_active_by_contact(
        self, contact_id: str, channel: Channel
    ) -> Conversation | None:
        """Active conversation for this contact on a specific channel."""
        ...

    @abstractmethod
    async def list_by_state(
        self,
        state: ConversationState,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]: ...

    @abstractmethod
    async def save(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    async def update(self, conversation: Conversation) -> Conversation: ...
