"""Converts text to embeddings using the configured OpenAI embedding model."""
from app.infrastructure.ai.openai.client import get_openai_client
from app.core.config import settings


async def embed_text(text: str) -> list[float]:
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding
