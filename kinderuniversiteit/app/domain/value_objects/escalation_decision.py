"""Value objects produced by the escalation rule engine."""
from __future__ import annotations

from dataclasses import dataclass

# Canonical definition lives in domain/enums — re-exported here so that
# existing imports from this module continue to work unchanged.
from app.domain.enums.escalation_trigger import EscalationTrigger

__all__ = ["EscalationTrigger", "EscalationDecision"]


@dataclass(frozen=True)
class EscalationDecision:
    should_escalate: bool
    trigger: EscalationTrigger | None = None
    reason: str = ""
    urgency: str = "normal"  # "high" | "normal"

    # When True the AI is bypassed entirely; human_message is returned directly
    # to the user.  Used for payment-status inquiries where a canned holding
    # reply is mandatory regardless of what the AI would say.
    hold_reply: bool = False
    human_message: str = ""

    @classmethod
    def no_escalation(cls) -> EscalationDecision:
        return cls(should_escalate=False)
