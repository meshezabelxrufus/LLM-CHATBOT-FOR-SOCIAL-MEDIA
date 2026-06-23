"""SQLAlchemy 2.0 async implementation of IContactRepository."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.contact_repository import IContactRepository
from app.core.logging import get_logger
from app.domain.entities.contact import Contact
from app.domain.enums.channel import Channel
from app.infrastructure.database.mappers import contact_to_domain
from app.infrastructure.database.models.contact_model import ContactModel

logger = get_logger(__name__)


class SQLContactRepository(IContactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Contact | None:
        stmt = select(ContactModel).where(ContactModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return contact_to_domain(model) if model else None

    async def get_by_external_id(
        self, external_id: str, channel: Channel
    ) -> Contact | None:
        stmt = select(ContactModel).where(
            ContactModel.external_id == external_id,
            ContactModel.channel == channel.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return contact_to_domain(model) if model else None

    async def upsert(self, contact: Contact) -> Contact:
        """Atomic INSERT … ON CONFLICT DO UPDATE keyed on (external_id, channel).

        Always refreshes last_seen_at, display_name, and locale so the record
        stays current without a separate SELECT-then-update round-trip.
        """
        now = datetime.now(tz=timezone.utc)

        stmt = (
            pg_insert(ContactModel)
            .values(
                id=contact.id,
                external_id=contact.external_id,
                channel=contact.channel.value,
                display_name=contact.display_name,
                locale=contact.locale,
                last_seen_at=now,
                metadata_=contact.metadata,
                created_at=contact.created_at,
            )
            .on_conflict_do_update(
                constraint="uq_contacts_external_channel",
                set_={
                    "display_name": contact.display_name,
                    "locale": contact.locale,
                    "last_seen_at": now,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Re-fetch so the returned entity has the server-generated id and timestamps.
        fetch = select(ContactModel).where(
            ContactModel.external_id == contact.external_id,
            ContactModel.channel == contact.channel.value,
        )
        result = await self._session.execute(fetch)
        model = result.scalar_one()

        logger.info(
            "contact_upserted",
            external_id=contact.external_id,
            channel=contact.channel.value,
        )
        return contact_to_domain(model)
