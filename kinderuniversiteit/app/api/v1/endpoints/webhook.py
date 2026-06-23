"""
POST /api/v1/webhook/manychat

Single entry-point for all ManyChat events across Facebook Messenger,
Instagram DM and WhatsApp.

Request lifecycle:
  1. Read raw body bytes (needed for HMAC verification before JSON parsing)
  2. Verify HMAC-SHA256 signature
  3. Parse JSON payload → IncomingMessage value object
  4. Rate-limit check per contact (Redis sliding window)
  5. Execute HandleIncomingMessage use case
  6. Build and return the ManyChat v2 response envelope

Error strategy:
  - Auth / parsing failures  → 401 / 400  (ManyChat will see an error)
  - Rate limit               → 429
  - AI or upstream failure   → 200 with a safe fallback message
    (returning 5xx causes ManyChat to retry, flooding the pipeline)
"""
from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.adapters.manychat.response_builder import (
    build_error_response,
    build_escalation_response,
    build_text_response,
)
from app.adapters.webhooks.manychat_webhook import parse_payload, verify_signature
from app.analytics.analytics_service import DBAnalyticsService
from app.api.dependencies.services import (
    get_analytics_service,
    get_conversation_memory_service,
    get_handle_incoming_message,
)
from app.application.services.conversation_memory_service import ConversationMemoryService
from app.application.use_cases.handle_incoming_message import HandleIncomingMessage
from app.core.constants import RATE_LIMIT_MESSAGES_PER_MINUTE
from app.core.exceptions import (
    AIServiceError,
    RateLimitError,
    WebhookAuthError,
    WebhookParsingError,
)
from app.core.logging import get_logger
from app.infrastructure.cache.redis_client import get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Human-readable fallback shown when the AI pipeline fails entirely.
_FALLBACK_NL = (
    "Bedankt voor je bericht. Er is een technisch probleem opgetreden. "
    "Ons team neemt zo snel mogelijk contact met je op."
)
_FALLBACK_EN = (
    "Thank you for your message. A technical issue occurred. "
    "Our team will get back to you as soon as possible."
)


@router.post("/manychat", status_code=status.HTTP_200_OK)
async def manychat_webhook(
    request: Request,
    x_manychat_signature: str = Header(default=""),
    use_case: HandleIncomingMessage = Depends(get_handle_incoming_message),
    memory: ConversationMemoryService = Depends(get_conversation_memory_service),
    analytics: DBAnalyticsService = Depends(get_analytics_service),
) -> dict:
    request_id = str(uuid.uuid4())
    _started_at = time.monotonic()

    log = logger.bind(request_id=request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)

    log.info("webhook_received", method=request.method, path=str(request.url.path))

    # ── 1. Read raw body ──────────────────────────────────────────────────────
    raw_body = await request.body()

    # ── 2. Verify signature ───────────────────────────────────────────────────
    try:
        verify_signature(raw_body, x_manychat_signature)
    except WebhookAuthError as exc:
        log.warning("webhook_auth_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # ── 3. Parse payload ──────────────────────────────────────────────────────
    try:
        payload = await request.json()
        incoming = parse_payload(payload)
    except WebhookParsingError as exc:
        log.warning("webhook_parse_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {exc}",
        )
    except Exception as exc:
        log.error("webhook_parse_unexpected", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse webhook payload",
        )

    log = log.bind(
        contact_id=incoming.contact_id,
        channel=incoming.channel.value,
    )
    log.info("webhook_parsed", text_preview=incoming.text[:80])

    # ── 4. Rate limit ─────────────────────────────────────────────────────────
    try:
        await _check_rate_limit(incoming.contact_id)
    except RateLimitError:
        log.warning("rate_limit_exceeded", contact_id=incoming.contact_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Please wait a moment.",
        )

    # ── 5. Execute use case ───────────────────────────────────────────────────
    try:
        reply_text = await use_case.execute(incoming)
    except (AIServiceError, Exception) as exc:
        error_type = type(exc).__name__
        log.error("pipeline_failed", error=str(exc), error_type=error_type, exc_info=True)
        response_time_ms = int((time.monotonic() - _started_at) * 1000)
        try:
            await analytics.record_fallback(
                contact_id=incoming.contact_id,
                channel=incoming.channel.value,
                error_type=error_type,
                response_time_ms=response_time_ms,
            )
        except Exception as analytics_exc:
            log.warning("fallback_analytics_failed", error=str(analytics_exc))
        fallback = _fallback_for_language(incoming.language)
        return build_error_response(fallback)

    # ── 6. Build ManyChat response ────────────────────────────────────────────
    # Check whether the conversation was just escalated so we can return the
    # escalation envelope instead of the normal text envelope.
    try:
        conversation = await memory.get_or_create_conversation(
            contact_id=incoming.contact_id,
            channel=incoming.channel,
            language=incoming.language,
        )
        if conversation.is_escalated:
            log.info("webhook_response_escalation")
            return build_escalation_response(reply_text)
    except Exception as exc:
        log.warning("escalation_state_check_failed", error=str(exc))

    log.info(
        "webhook_response_ok",
        reply_len=len(reply_text),
        response_time_ms=int((time.monotonic() - _started_at) * 1000),
    )
    return build_text_response(reply_text)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _check_rate_limit(contact_id: str) -> None:
    """Sliding-window rate limit: max N messages per contact per minute.

    Uses a Redis counter with a 60-second TTL. The counter is set to expire
    on first increment so the window resets naturally without a cron job.
    """
    redis = await get_redis()
    key = f"ratelimit:webhook:{contact_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > RATE_LIMIT_MESSAGES_PER_MINUTE:
        raise RateLimitError(f"Contact {contact_id} exceeded rate limit")


def _fallback_for_language(language: str) -> str:
    return _FALLBACK_EN if language == "en" else _FALLBACK_NL
