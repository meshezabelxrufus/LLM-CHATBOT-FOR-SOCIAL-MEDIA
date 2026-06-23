"""Application-wide exception hierarchy."""


class AppError(Exception):
    """Base for all application errors."""


class ConfigurationError(AppError):
    """A required config value is missing or invalid."""


class WebhookAuthError(AppError):
    """Webhook signature verification failed."""


class WebhookParsingError(AppError):
    """Webhook payload is missing required fields or has an unexpected structure."""


class AIServiceError(AppError):
    """OpenAI or RAG pipeline failure."""


class KnowledgeBaseError(AppError):
    """ChromaDB / document ingestion failure."""


class ConversationNotFoundError(AppError):
    """No conversation found for the given ID."""


class EscalationError(AppError):
    """Escalation routing or notification failure."""


class RateLimitError(AppError):
    """Per-user or global rate limit exceeded."""
