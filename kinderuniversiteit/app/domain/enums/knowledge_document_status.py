from enum import StrEnum


class KnowledgeDocumentStatus(StrEnum):
    PENDING = "pending"         # uploaded, not yet ingested
    PROCESSING = "processing"   # chunking / embedding in progress
    READY = "ready"             # vectors stored in ChromaDB
    FAILED = "failed"           # ingestion error; see error_message
