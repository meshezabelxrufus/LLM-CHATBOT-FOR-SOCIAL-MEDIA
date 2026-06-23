"""Pure domain entity — no ORM, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState


@dataclass
class Conversation:
    contact_id: str
    channel: Channel
    id: UUID = field(default_factory=uuid4)
    state: ConversationState = ConversationState.ACTIVE
    language: str = "nl"
    last_interaction_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_escalated(self) -> bool:
        return self.state == ConversationState.ESCALATED

    @property
    def is_active(self) -> bool:
        return self.state == ConversationState.ACTIVE
