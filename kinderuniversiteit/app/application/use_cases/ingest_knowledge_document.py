"""Add or update a single pre-chunked document in the vector knowledge base."""
from app.application.interfaces.knowledge_base import IKnowledgeBase


class IngestKnowledgeDocument:
    def __init__(self, knowledge_base: IKnowledgeBase) -> None:
        self._kb = knowledge_base

    async def execute(self, doc_id: str, content: str, metadata: dict) -> None:
        await self._kb.ingest_document(doc_id, content, metadata)
