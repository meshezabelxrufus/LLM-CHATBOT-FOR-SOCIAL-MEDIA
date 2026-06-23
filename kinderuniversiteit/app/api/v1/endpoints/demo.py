"""
POST /demo/chat — stateless demo endpoint for the frontend presentation.

Accepts a user message + optional conversation history.
Runs the full RAG + LLM pipeline without touching the database.
Returns the assistant reply as plain text.
"""
from __future__ import annotations

import re
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies.services import get_ai_service, get_knowledge_base, get_prompt_manager
from app.infrastructure.ai.openai.ai_service import OpenAIService

router = APIRouter(prefix="/demo", tags=["Demo"])

_ESCALATE_RE = re.compile(r"\[ESCALATE\].*", re.DOTALL)


class HistoryEntry(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryEntry] = []


class ChatResponse(BaseModel):
    reply: str
    confidence: float
    sources: list[str]


@router.post("/chat", response_model=ChatResponse)
async def demo_chat(
    body: ChatRequest,
    ai_service: OpenAIService = Depends(get_ai_service),
) -> ChatResponse:
    history = [{"role": e.role, "content": e.content} for e in body.history]

    result = await ai_service.generate_response(
        conversation_id=uuid4(),
        user_message=body.message,
        history=history,  # type: ignore[arg-type]
    )

    # Strip the [ESCALATE] block before returning to the UI — the signal is
    # for internal escalation logic only; the customer-facing text precedes it.
    reply = _ESCALATE_RE.sub("", result.text).strip()

    return ChatResponse(
        reply=reply,
        confidence=result.confidence_score,
        sources=result.sources,
    )
