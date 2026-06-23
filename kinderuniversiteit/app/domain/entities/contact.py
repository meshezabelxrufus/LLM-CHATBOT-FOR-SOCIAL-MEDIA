"""Pure domain entity — no ORM, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums.channel import Channel


@dataclass
class Contact:
    external_id: str
    channel: Channel
    id: UUID = field(default_factory=uuid4)
    display_name: str = ""
    locale: str = "nl"
    last_seen_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
