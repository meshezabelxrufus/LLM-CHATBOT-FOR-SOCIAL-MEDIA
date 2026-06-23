"""
Async HTTP client for the ManyChat API.

Used for proactive / out-of-band messaging — sending a message to a subscriber
outside of an active webhook response cycle (e.g. escalation notifications,
follow-up messages after a delay).

For synchronous webhook replies the response envelope returned by the endpoint
is sufficient; this client is only needed for async delivery.

ManyChat API base: https://api.manychat.com
All endpoints require:  Authorization: Bearer <PAGE_ACCESS_TOKEN>

Channel-specific send paths:
  Facebook  → /fb/sending/sendContent
  Instagram → /instagram/sending/sendContent
  WhatsApp  → /whatsapp/sending/sendContent
"""
from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.domain.enums.channel import Channel

logger = get_logger(__name__)

# ManyChat send-content endpoint per channel.
_SEND_PATHS: dict[Channel, str] = {
    Channel.FACEBOOK: "/fb/sending/sendContent",
    Channel.INSTAGRAM: "/instagram/sending/sendContent",
    Channel.WHATSAPP: "/whatsapp/sending/sendContent",
}

# ManyChat tag endpoint per channel.
_TAG_PATHS: dict[Channel, str] = {
    Channel.FACEBOOK: "/fb/subscriber/addTagByName",
    Channel.INSTAGRAM: "/instagram/subscriber/addTagByName",
    Channel.WHATSAPP: "/whatsapp/subscriber/addTagByName",
}

_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


class ManyChatClient:
    def __init__(self) -> None:
        self._base_url = settings.manychat_base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {settings.manychat_api_key}",
            "Content-Type": "application/json",
        }

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_text_message(
        self,
        subscriber_id: str,
        text: str,
        channel: Channel = Channel.FACEBOOK,
    ) -> dict:
        """Send a plain text message to a ManyChat subscriber.

        Returns the ManyChat API response body on success.
        Raises AIServiceError on non-retryable API errors.
        """
        path = _SEND_PATHS[channel]
        body = {
            "subscriber_id": subscriber_id,
            "data": {
                "version": "v2",
                "content": {
                    "messages": [{"type": "text", "text": text}],
                    "actions": [],
                    "quick_replies": [],
                },
            },
        }
        return await self._post(path, body)

    async def tag_subscriber(
        self,
        subscriber_id: str,
        tag: str,
        channel: Channel = Channel.FACEBOOK,
    ) -> dict:
        """Apply a named tag to a ManyChat subscriber."""
        path = _TAG_PATHS[channel]
        body = {"subscriber_id": subscriber_id, "tag_name": tag}
        return await self._post(path, body)

    async def set_custom_field(
        self,
        subscriber_id: str,
        field_name: str,
        value: str,
        channel: Channel = Channel.FACEBOOK,
    ) -> dict:
        """Set a custom field on a ManyChat subscriber."""
        channel_prefix = _channel_prefix(channel)
        path = f"/{channel_prefix}/subscriber/setCustomFieldByName"
        body = {
            "subscriber_id": subscriber_id,
            "field_name": field_name,
            "field_value": value,
        }
        return await self._post(path, body)

    # ── Internal HTTP ─────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base_url}{path}"
        logger.info("manychat_api_request", path=path)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=body, headers=self._headers)

        if response.status_code == 429:
            logger.warning("manychat_rate_limited", path=path)
            raise httpx.TimeoutException("ManyChat rate limit — will retry", request=response.request)

        if not response.is_success:
            logger.error(
                "manychat_api_error",
                path=path,
                status=response.status_code,
                body=response.text[:200],
            )
            raise AIServiceError(
                f"ManyChat API error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        logger.info("manychat_api_ok", path=path, status=response.status_code)
        return data


# ── Helpers ───────────────────────────────────────────────────────────────────


def _channel_prefix(channel: Channel) -> str:
    return {
        Channel.FACEBOOK: "fb",
        Channel.INSTAGRAM: "instagram",
        Channel.WHATSAPP: "whatsapp",
    }[channel]
