"""POST /api/v1/knowledge/* — admin endpoints for managing the knowledge base."""
from fastapi import APIRouter, Depends

from app.api.dependencies.services import get_knowledge_base
from app.infrastructure.ai.rag.knowledge_base_service import ChromaKnowledgeBase
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


class IngestRequest(BaseModel):
    doc_id: str
    content: str
    metadata: dict = {}


@router.post("/ingest")
async def ingest_document(
    body: IngestRequest,
    kb: ChromaKnowledgeBase = Depends(get_knowledge_base),
) -> dict:
    await kb.ingest_document(body.doc_id, body.content, body.metadata)
    return {"status": "ingested", "doc_id": body.doc_id}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    kb: ChromaKnowledgeBase = Depends(get_knowledge_base),
) -> dict:
    await kb.delete_document(doc_id)
    return {"status": "deleted", "doc_id": doc_id}
