from abc import ABC, abstractmethod
from uuid import UUID

from openai.types.chat import ChatCompletionMessageParam

from app.domain.value_objects.ai_response import AIResponse


class IAIService(ABC):
    @abstractmethod
    async def generate_response(
        self,
        conversation_id: UUID,
        user_message: str,
        history: list[ChatCompletionMessageParam],
    ) -> AIResponse: ...
