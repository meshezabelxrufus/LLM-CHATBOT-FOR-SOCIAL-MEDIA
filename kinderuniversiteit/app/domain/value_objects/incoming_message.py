"""Immutable value object representing an inbound message from any channel."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums.channel import Channel


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class IncomingMessage:
    contact_id: str
    channel: Channel
    text: str
    raw_payload: dict
    display_name: str = ""
    locale: str = "nl"
    timestamp: datetime = field(default_factory=_now_utc)

    @property
    def language(self) -> str:
        """ISO 639-1 language code derived from the locale tag (e.g. 'nl_NL' → 'nl')."""
        return self.locale.split("_")[0].lower() if self.locale else "nl"
