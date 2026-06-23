"""
Parses and authenticates raw ManyChat webhook payloads.

ManyChat sends a single JSON structure regardless of the originating channel
(Facebook Messenger, Instagram DM, WhatsApp). This adapter:

  1. Verifies the HMAC-SHA256 signature so only genuine ManyChat events proceed.
  2. Detects the channel from the payload's channel identifier.
  3. Normalises two distinct payload schemas ManyChat uses (direct subscriber
     object vs. nested message object) into a single IncomingMessage value object.

ManyChat channel identifiers → our Channel enum:
  "fb" | "facebook" | "messenger"  →  Channel.FACEBOOK
  "ig" | "instagram"               →  Channel.INSTAGRAM
  "wa" | "whatsapp"                →  Channel.WHATSAPP
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import WebhookAuthError, WebhookParsingError
from app.core.logging import get_logger
from app.domain.enums.channel import Channel
from app.domain.value_objects.incoming_message import IncomingMessage

logger = get_logger(__name__)

# ManyChat channel identifier strings mapped to our enum.
_CHANNEL_MAP: dict[str, Channel] = {
    "fb": Channel.FACEBOOK,
    "facebook": Channel.FACEBOOK,
    "messenger": Channel.FACEBOOK,
    "ig": Channel.INSTAGRAM,
    "instagram": Channel.INSTAGRAM,
    "wa": Channel.WHATSAPP,
    "whatsapp": Channel.WHATSAPP,
}

# Fallback text when ManyChat sends an empty message body.
_EMPTY_TEXT = "(no message text)"


# ── Signature verification ────────────────────────────────────────────────────


def verify_signature(payload: bytes, signature: str) -> None:
    """Raise WebhookAuthError if the HMAC-SHA256 digest does not match.

    ManyChat may send the signature as a bare hex digest or prefixed with
    'sha256=' — both formats are handled.

    Verification is skipped (with a warning) when `manychat_webhook_secret`
    is not configured, to allow local development without a real secret.
    """
    if not settings.manychat_webhook_secret:
        if settings.is_production:
            raise WebhookAuthError("Webhook secret not configured in production")
        logger.warning("webhook_signature_check_skipped", reason="no secret configured")
        return

    # Strip optional prefix.
    sig_hex = signature.removeprefix("sha256=").strip()

    expected = hmac.new(
        settings.manychat_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, sig_hex):
        raise WebhookAuthError("Invalid ManyChat webhook signature")


# ── Payload parsing ───────────────────────────────────────────────────────────


def parse_payload(payload: dict) -> IncomingMessage:
    """Map the raw ManyChat JSON payload to an IncomingMessage value object.

    Handles two schemas ManyChat may send:

    Schema A — flat subscriber object (most common for External Request flows):
        {
            "id": "subscriber_id",
            "name": "John Doe",
            "channel": "fb",
            "last_input_text": "User's message",
            "locale": "nl_NL",
            "last_interaction": "2026-06-22 10:00:00"
        }

    Schema B — nested message object (used by some webhook automations):
        {
            "subscriber": {"id": "...", "name": "...", "channel": "fb", "locale": "nl_NL"},
            "message": {"text": "User's message"},
            "timestamp": 1719043200
        }
    """
    try:
        if "subscriber" in payload:
            return _parse_schema_b(payload)
        return _parse_schema_a(payload)
    except WebhookParsingError:
        raise
    except Exception as exc:
        raise WebhookParsingError(f"Unexpected payload structure: {exc}") from exc


def _parse_schema_a(payload: dict) -> IncomingMessage:
    """Flat subscriber object — standard ManyChat External Request payload."""
    contact_id = _require_str(payload, "id", "subscriber id")
    text = (payload.get("last_input_text") or _EMPTY_TEXT).strip() or _EMPTY_TEXT
    channel = _resolve_channel(payload)
    display_name = _extract_display_name(payload)
    locale = payload.get("locale") or "nl"
    timestamp = _parse_timestamp(payload.get("last_interaction"))

    return IncomingMessage(
        contact_id=contact_id,
        channel=channel,
        text=text,
        display_name=display_name,
        locale=locale,
        timestamp=timestamp,
        raw_payload=payload,
    )


def _parse_schema_b(payload: dict) -> IncomingMessage:
    """Nested subscriber + message object schema."""
    subscriber = payload.get("subscriber") or {}
    message = payload.get("message") or {}

    contact_id = _require_str(subscriber, "id", "subscriber.id")
    text = (message.get("text") or _EMPTY_TEXT).strip() or _EMPTY_TEXT
    channel = _resolve_channel(subscriber)
    display_name = _extract_display_name(subscriber)
    locale = subscriber.get("locale") or "nl"
    timestamp = _parse_timestamp(payload.get("timestamp"))

    return IncomingMessage(
        contact_id=contact_id,
        channel=channel,
        text=text,
        display_name=display_name,
        locale=locale,
        timestamp=timestamp,
        raw_payload=payload,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _resolve_channel(source: dict) -> Channel:
    """Find the channel identifier in any of the fields ManyChat may use."""
    raw = (
        source.get("channel")
        or source.get("channel_type")
        or source.get("source")
        or ""
    ).lower().strip()

    channel = _CHANNEL_MAP.get(raw)
    if channel is None:
        raise WebhookParsingError(
            f"Unrecognised channel identifier '{raw}'. "
            f"Expected one of: {list(_CHANNEL_MAP.keys())}"
        )
    return channel


def _extract_display_name(source: dict) -> str:
    """Prefer the pre-built 'name' field; fall back to first + last."""
    if name := source.get("name", "").strip():
        return name
    first = source.get("first_name", "").strip()
    last = source.get("last_name", "").strip()
    return f"{first} {last}".strip()


def _require_str(source: dict, key: str, label: str) -> str:
    value = source.get(key)
    if not value or not str(value).strip():
        raise WebhookParsingError(f"Required field '{label}' is missing or empty")
    return str(value).strip()


def _parse_timestamp(raw: str | int | float | None) -> datetime:
    """Parse ManyChat's timestamp into a timezone-aware datetime.

    ManyChat sends timestamps in two formats:
      - ISO-like string: "2026-06-22 10:00:00"
      - Unix epoch integer
    """
    if raw is None:
        return datetime.now(tz=timezone.utc)
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        # ManyChat sends naive strings — assume UTC.
        return datetime.strptime(raw if isinstance(raw, str) else str(raw), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, OSError):
        logger.warning("timestamp_parse_failed", raw=raw)
        return datetime.now(tz=timezone.utc)
