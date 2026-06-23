"""
Builds ManyChat-compatible response payloads.

ManyChat External Request actions expect a v2 envelope in the HTTP response.
The AI reply is delivered directly to the subscriber by ManyChat once it
receives this envelope — no separate API call is needed for synchronous flows.

Envelope structure:
    {
        "version": "v2",
        "content": {
            "messages":      [...],   # text blocks shown to the subscriber
            "actions":       [...],   # CRM / field mutations inside ManyChat
            "quick_replies": [...]    # optional tap-to-reply buttons
        }
    }

For escalations we add a set_field action so ManyChat can branch its own
flow to the human handoff sequence without any extra API call.
"""
from __future__ import annotations


# ── Public builders ───────────────────────────────────────────────────────────


def build_text_response(
    text: str,
    quick_replies: list[dict] | None = None,
) -> dict:
    """Wrap a plain text reply in the ManyChat v2 response envelope."""
    return {
        "version": "v2",
        "content": {
            "messages": [_text_block(text)],
            "actions": [],
            "quick_replies": quick_replies or [],
        },
    }


def build_escalation_response(handoff_message: str) -> dict:
    """Build a response that notifies the subscriber and signals ManyChat to
    route to the human-agent flow via a custom field mutation.

    The 'needs_human_agent' field must be created in ManyChat's Custom Fields
    and used as a condition in the handoff flow.
    """
    return {
        "version": "v2",
        "content": {
            "messages": [_text_block(handoff_message)],
            "actions": [
                _set_field("needs_human_agent", "true"),
                _set_field("escalation_reason", "ai_confidence_low"),
            ],
            "quick_replies": [],
        },
    }


def build_error_response(fallback_text: str) -> dict:
    """Safe fallback returned when the AI pipeline fails.

    Always returns a valid ManyChat envelope so the subscriber sees a message
    instead of a broken flow.
    """
    return build_text_response(fallback_text)


# ── Private helpers ───────────────────────────────────────────────────────────


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _set_field(field_name: str, value: str) -> dict:
    return {"action": "set_field", "field_name": field_name, "value": value}
