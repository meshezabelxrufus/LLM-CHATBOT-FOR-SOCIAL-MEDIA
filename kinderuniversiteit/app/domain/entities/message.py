"""Pure domain entity — no ORM, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums.message_role import MessageRole


@dataclass
class Message:
    conversation_id: UUID
    role: MessageRole
    content: str
    id: UUID = field(default_factory=uuid4)
    tokens_used: int = 0
    confidence_score: float | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
