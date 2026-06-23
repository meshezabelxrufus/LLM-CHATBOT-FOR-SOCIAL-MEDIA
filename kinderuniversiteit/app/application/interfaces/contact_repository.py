"""Abstract contact repository — application layer depends on this port."""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.contact import Contact
from app.domain.enums.channel import Channel


class IContactRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Contact | None: ...

    @abstractmethod
    async def get_by_external_id(
        self, external_id: str, channel: Channel
    ) -> Contact | None: ...

    @abstractmethod
    async def upsert(self, contact: Contact) -> Contact:
        """Insert or update a contact record keyed on (external_id, channel).
        Always updates last_seen_at, display_name, and locale on conflict."""
        ...
