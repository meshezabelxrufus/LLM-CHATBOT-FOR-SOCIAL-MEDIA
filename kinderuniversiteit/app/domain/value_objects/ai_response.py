"""Immutable value object returned by the AI pipeline."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AIResponse:
    text: str
    confidence_score: float
    tokens_used: int
    requires_escalation: bool
    sources: list[str]  # document IDs used from the knowledge base
