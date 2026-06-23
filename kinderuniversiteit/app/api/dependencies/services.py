"""
Dependency injection wiring.

Each `get_*` function is a FastAPI dependency that constructs concrete
implementations and injects them into endpoints and use cases.

All repositories created here share the same AsyncSession per request,
so every operation inside one HTTP handler runs in a single transaction.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.analytics_service import DBAnalyticsService
from app.api.dependencies.database import get_session
from app.application.interfaces.analytics_repository import IAnalyticsRepository
from app.application.services.conversation_memory_service import ConversationMemoryService
from app.application.use_cases.handle_incoming_message import HandleIncomingMessage
from app.infrastructure.ai.anthropic.ai_service import AnthropicService
from app.infrastructure.ai.openai.ai_service import OpenAIService
from app.infrastructure.ai.rag.knowledge_base_service import ChromaKnowledgeBase
from app.infrastructure.database.repositories.analytics_repository import SQLAnalyticsRepository
from app.infrastructure.database.repositories.contact_repository import SQLContactRepository
from app.infrastructure.database.repositories.conversation_repository import SQLConversationRepository
from app.infrastructure.database.repositories.escalation_repository import SQLEscalationRepository
from app.infrastructure.database.repositories.message_repository import SQLMessageRepository
from app.prompts.prompt_manager import PromptManager
from app.core.config import settings
from app.application.interfaces.ai_service import IAIService


def get_knowledge_base() -> ChromaKnowledgeBase:
    return ChromaKnowledgeBase()


def get_prompt_manager() -> PromptManager:
    return PromptManager()


def get_ai_service(
    kb: ChromaKnowledgeBase = Depends(get_knowledge_base),
    pm: PromptManager = Depends(get_prompt_manager),
) -> IAIService:
    if settings.ai_provider == "anthropic":
        return AnthropicService(knowledge_base=kb, prompt_manager=pm)
    return OpenAIService(knowledge_base=kb, prompt_manager=pm)


def get_conversation_memory_service(
    session: AsyncSession = Depends(get_session),
) -> ConversationMemoryService:
    return ConversationMemoryService(
        conversation_repo=SQLConversationRepository(session),
        message_repo=SQLMessageRepository(session),
        contact_repo=SQLContactRepository(session),
        escalation_repo=SQLEscalationRepository(session),
    )


def get_analytics_service(
    session: AsyncSession = Depends(get_session),
) -> DBAnalyticsService:
    return DBAnalyticsService(session)


def get_analytics_repository(
    session: AsyncSession = Depends(get_session),
) -> IAnalyticsRepository:
    return SQLAnalyticsRepository(session)


def get_handle_incoming_message(
    memory: ConversationMemoryService = Depends(get_conversation_memory_service),
    ai_service: OpenAIService = Depends(get_ai_service),
    analytics: DBAnalyticsService = Depends(get_analytics_service),
) -> HandleIncomingMessage:
    return HandleIncomingMessage(
        memory=memory,
        ai_service=ai_service,
        analytics_service=analytics,
    )
