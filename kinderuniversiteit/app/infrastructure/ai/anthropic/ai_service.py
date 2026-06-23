"""Concrete IAIService for Anthropic (Claude) — RAG retrieval then LLM call."""
from __future__ import annotations

from uuid import UUID
from anthropic import AsyncAnthropic

from openai.types.chat import ChatCompletionMessageParam

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.knowledge_base import IKnowledgeBase
from app.core.config import settings
from app.core.constants import RAG_SIMILARITY_THRESHOLD, RAG_TOP_K
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.domain.value_objects.ai_response import AIResponse
from app.prompts.prompt_manager import PromptManager

logger = get_logger(__name__)
_SEPARATOR = "-" * 51


class AnthropicService(IAIService):
    def __init__(self, knowledge_base: IKnowledgeBase, prompt_manager: PromptManager) -> None:
        self._kb = knowledge_base
        self._prompts = prompt_manager
        # Ensure we only construct client if key exists to prevent init failures
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

    async def generate_response(
        self,
        conversation_id: UUID,
        user_message: str,
        history: list[ChatCompletionMessageParam],
    ) -> AIResponse:
        if not self._client:
            raise AIServiceError("Anthropic client is not initialized (API key missing).")

        # ── 1. RAG retrieval ─────────────────────────────────────────────────
        try:
            chunks = await self._kb.search(user_message, top_k=RAG_TOP_K)
        except Exception as exc:
            logger.warning("rag_search_failed", error=str(exc), conversation_id=str(conversation_id))
            chunks = []

        self._log_retrieval(user_message, chunks)

        # ── 2. Build system prompt ────────────────────────────────────────────
        try:
            system_prompt = self._prompts.system_prompt(channel="messaging", language="auto")
        except Exception:
            system_prompt = "You are a helpful customer support assistant for Kinderuniversiteit."

        if chunks:
            try:
                rag_block = self._prompts.rag_context_prompt(chunks)
                system_prompt = f"{system_prompt}\n\n{rag_block}"
            except Exception as exc:
                logger.warning("rag_prompt_render_failed", error=str(exc))

        # ── 3. Assemble input messages ────────────────────────────────────────
        # Convert OpenAI format history to Anthropic format
        anthropic_messages = []
        for msg in history:
            role = msg.get("role")
            if role == "system":
                # System prompts are handled at the top level in Anthropic API
                continue
            anthropic_messages.append({
                "role": "user" if role == "user" else "assistant",
                "content": str(msg.get("content", ""))
            })

        anthropic_messages.append({"role": "user", "content": user_message})

        # ── 4. Call LLM ───────────────────────────────────────────────────────
        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
                temperature=settings.anthropic_temperature,
                system=system_prompt,
                messages=anthropic_messages,
            )
        except Exception as exc:
            logger.error(
                "llm_call_failed",
                error=str(exc),
                conversation_id=str(conversation_id),
            )
            raise AIServiceError(f"LLM call failed: {exc}") from exc

        # ── 5. Extract text and usage ─────────────────────────────────────────
        try:
            raw_text: str = response.content[0].text
            tokens_used: int = response.usage.input_tokens + response.usage.output_tokens
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIServiceError(f"Unexpected response structure: {exc}") from exc

        # ── 6. Confidence from RAG similarity ─────────────────────────────────
        if chunks:
            confidence_score = round(
                sum(c.get("similarity", 0.0) for c in chunks) / len(chunks), 4
            )
        else:
            confidence_score = 0.0

        # ── 7. Escalation signal ──────────────────────────────────────────────
        requires_escalation = "[ESCALATE]" in raw_text

        # ── 8. Collect source doc IDs ─────────────────────────────────────────
        sources = [
            c.get("metadata", {}).get("doc_id", "")
            for c in chunks
            if c.get("metadata", {}).get("doc_id")
        ]

        logger.info(
            "ai_response_generated",
            conversation_id=str(conversation_id),
            chunks_retrieved=len(chunks),
            confidence_score=confidence_score,
            tokens_used=tokens_used,
            requires_escalation=requires_escalation,
        )

        return AIResponse(
            text=raw_text,
            confidence_score=confidence_score,
            tokens_used=tokens_used,
            requires_escalation=requires_escalation,
            sources=sources,
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _log_retrieval(self, question: str, chunks: list[dict]) -> None:
        lines = [
            "===================================================",
            "QUESTION",
            question,
            _SEPARATOR,
            f"Retrieved Chunks  ({len(chunks)} above threshold={RAG_SIMILARITY_THRESHOLD})",
        ]

        if not chunks:
            lines.append("  *** ZERO CHUNKS RETRIEVED — LLM will receive no knowledge context ***")
        else:
            for i, chunk in enumerate(chunks, 1):
                meta = chunk.get("metadata", {})
                lines += [
                    f"\n  Chunk {i}",
                    f"    Similarity : {chunk.get('similarity', 'n/a')}",
                    f"    Source     : {meta.get('source_file', 'unknown')}  p{meta.get('page_number', '?')}",
                    f"    doc_id     : {meta.get('doc_id', 'unknown')}",
                    f"    Text       : {chunk.get('content', '')[:200]!r}",
                ]

        logger.info("rag_debug", report="\n".join(lines))
