"""Pure domain entity — no ORM, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Escalation:
    conversation_id: UUID
    reason: str
    id: UUID = field(default_factory=uuid4)
    resolved: bool = False
    agent_id: str | None = None
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
