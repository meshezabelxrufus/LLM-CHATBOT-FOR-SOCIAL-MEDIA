from abc import ABC, abstractmethod


class IKnowledgeBase(ABC):
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[dict]: ...

    @abstractmethod
    async def ingest_document(self, doc_id: str, content: str, metadata: dict) -> None: ...

    @abstractmethod
    async def delete_document(self, doc_id: str) -> None: ...
