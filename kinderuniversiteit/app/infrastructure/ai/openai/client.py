"""LLM client — routes to Anthropic SDK or OpenAI-compatible SDK based on the API key.

- sk-ant-* keys  →  Anthropic AsyncAnthropic client (claude-* models)
- anything else  →  AsyncOpenAI (supports OpenAI, Gemini, Azure, etc.)

Both paths return a duck-typed _ChatCompletion that exposes:
    .choices[0].message.content  (str)
    .usage.total_tokens          (int)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Minimal response adapter ──────────────────────────────────────────────────

@dataclass
class _Msg:
    content: str


@dataclass
class _Choice:
    message: _Msg


@dataclass
class _Usage:
    total_tokens: int


@dataclass
class _ChatCompletion:
    choices: list[_Choice]
    usage: _Usage


# ── OpenAI-compatible client ──────────────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _openai_client = AsyncOpenAI(**kwargs)
    return _openai_client


# ── Anthropic client ──────────────────────────────────────────────────────────

_anthropic_client: Any = None


def _get_anthropic_client() -> Any:
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic
        _anthropic_client = AsyncAnthropic(api_key=settings.openai_api_key)
    return _anthropic_client


def _is_anthropic_key() -> bool:
    return settings.openai_api_key.startswith("sk-ant-")


# ── Unified chat_completion ───────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def chat_completion(
    messages: list[ChatCompletionMessageParam],
    *,
    instructions: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> _ChatCompletion:
    """Call the active LLM provider and return a normalised response.

    `instructions` is treated as a system message regardless of provider.
    """
    temp = temperature if temperature is not None else settings.openai_temperature

    if _is_anthropic_key():
        return await _anthropic_chat(messages, system=instructions, temperature=temp)
    else:
        return await _openai_chat(messages, system=instructions, temperature=temp, **kwargs)


async def _anthropic_chat(
    messages: list[ChatCompletionMessageParam],
    *,
    system: str | None,
    temperature: float,
) -> _ChatCompletion:
    client = _get_anthropic_client()

    # Anthropic requires alternating user/assistant turns — filter any stray
    # system messages that may have been injected into the history.
    ant_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]

    kwargs: dict[str, Any] = dict(
        model=settings.openai_model,
        max_tokens=settings.openai_max_tokens,
        temperature=temperature,
        messages=ant_messages,
    )
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)

    content = response.content[0].text if response.content else ""
    total = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
    return _ChatCompletion(
        choices=[_Choice(message=_Msg(content=content))],
        usage=_Usage(total_tokens=total),
    )


async def _openai_chat(
    messages: list[ChatCompletionMessageParam],
    *,
    system: str | None,
    temperature: float,
    **kwargs,
) -> _ChatCompletion:
    from typing import cast
    from openai.types.chat import ChatCompletion

    client = get_openai_client()

    full_messages: list[ChatCompletionMessageParam] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=full_messages,
        max_tokens=settings.openai_max_tokens,
        temperature=temperature,
        stream=False,
        **kwargs,
    )
    oai = cast(ChatCompletion, response)
    content = oai.choices[0].message.content or ""
    total = oai.usage.total_tokens if oai.usage else 0
    return _ChatCompletion(
        choices=[_Choice(message=_Msg(content=content))],
        usage=_Usage(total_tokens=total),
    )
