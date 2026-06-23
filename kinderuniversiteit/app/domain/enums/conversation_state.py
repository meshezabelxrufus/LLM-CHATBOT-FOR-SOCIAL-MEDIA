from enum import StrEnum


class ConversationState(StrEnum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"
    RESOLVED = "resolved"  # agent confirmed resolution; re-opens as ACTIVE on new message
