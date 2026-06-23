"""
Async embedding service wrapping the OpenAI embeddings API.

Supports single and batch embedding. Batches are capped at BATCH_SIZE to stay
well below OpenAI's per-request token limit. Each batch retries independently
on rate-limit and timeout errors so one transient failure doesn't abort the run.
"""
import asyncio
from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.ai.openai.client import get_openai_client

logger = get_logger(__name__)

# OpenAI allows up to 2 048 inputs per request, but large batches hit token limits.
# 96 is a safe default for typical knowledge-base text chunks (~500 chars each).
BATCH_SIZE = 96


class EmbeddingService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or get_openai_client()
        self._model = settings.openai_embedding_model

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single string. Normalises whitespace before sending."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(
        self, texts: list[str], batch_size: int = BATCH_SIZE
    ) -> list[list[float]]:
        """
        Embed a list of strings, splitting into sub-batches of `batch_size`.
        Sub-batches are sent sequentially to respect rate limits; each sub-batch
        retries on its own before failing.
        """
        if not texts:
            return []

        normalised = [t.replace("\n", " ").strip() for t in texts]
        batches = [normalised[i : i + batch_size] for i in range(0, len(normalised), batch_size)]

        embeddings: list[list[float]] = []
        for idx, batch in enumerate(batches):
            logger.info("embedding_batch", batch=idx + 1, total=len(batches), size=len(batch))
            response = await self._embed_batch_with_retry(batch)
            embeddings.extend(item.embedding for item in response.data)

        return embeddings

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        reraise=True,
    )
    async def _embed_batch_with_retry(self, texts: list[str]):
        return await self._client.embeddings.create(model=self._model, input=texts)


_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
