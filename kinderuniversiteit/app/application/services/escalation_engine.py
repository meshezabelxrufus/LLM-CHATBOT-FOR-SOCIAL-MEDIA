"""
Escalation rule engine.

Determines whether a conversation should be escalated to a human agent by
applying two complementary detection passes:

  Pre-AI  — runs on the raw user message BEFORE calling OpenAI.
            Catches payment-status inquiries and financial-data requests via
            keyword patterns so we can bypass the AI entirely when the rule
            mandates a canned holding reply.

  Post-AI — runs on the AIResponse AFTER OpenAI returns.
            Parses the machine-readable [ESCALATE]…[/ESCALATE] block the
            system prompt instructs the model to emit, and also falls back to
            the confidence-score threshold.

Both passes return an EscalationDecision.  The caller (HandleIncomingMessage)
decides which decision wins; the two passes are never merged internally so the
logic stays easy to test in isolation.

Escalation rules
────────────────
PAYMENT_STATUS   User asks about their own payment / confirmation.
                 → hold_reply=True (skip AI, return holding message)
                 → urgency="high"

FINANCIAL_REQUEST  User requests bank details, a refund, or account data.
                 → hold_reply=False (AI responds per system-prompt rules)
                 → escalate in background so a human can follow up
                 → urgency="normal"

AI_SIGNAL        AI emits [ESCALATE] block or sets requires_escalation=True.
                 → hold_reply=False, AI reply already contains user-facing text

LOW_CONFIDENCE   AI confidence_score < configured threshold.
                 → hold_reply=False
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.value_objects.ai_response import AIResponse
from app.domain.value_objects.escalation_decision import EscalationDecision, EscalationTrigger

logger = get_logger(__name__)

# ── Pattern lists ──────────────────────────────────────────────────────────────
# All patterns are compiled case-insensitively.  Word boundaries (\b) prevent
# spurious matches inside longer words (e.g. "behandeling" ≠ "betaling").

_PAYMENT_STATUS_RAW: list[str] = [
    # Dutch
    r"\bbetaalbevestig",          # betaalbevestiging, betaalbevestigd
    r"\bbetalingsbevestig",       # betalingsbevestiging
    r"\bik\s+heb\s+betaald\b",
    r"\bheb\s+ik\s+betaald\b",
    r"\bmijn\s+betaling\b",
    r"\bbetaling\s+ontvangen",
    r"\bis\s+mijn\s+betaling",
    r"\bbetaling\s+verwerkt",
    r"\bik\s+betaalde?\b",
    # English
    r"\bpayment\s+confirm",       # payment confirmation, payment confirmed
    r"\bconfirm.*payment",
    r"\bi\s+paid\b",
    r"\bi\s+have\s+paid\b",
    r"\bdid\s+you\s+receive\s+my\s+payment",
    r"\bpayment\s+received",
    r"\bpayment\s+processed",
    r"\bmy\s+payment\b",
    r"\bpayment\s+status",
]

_FINANCIAL_REQUEST_RAW: list[str] = [
    # Bank-account / IBAN requests
    r"\brekeningnummer\b",
    r"\biban\b",
    r"\bbankrekening\b",
    r"\bbank\s+account\b",
    r"\baccount\s+number\b",
    # Refund / money back
    r"\bterugbetaling\b",
    r"\bgeld\s+terug\b",
    r"\bteruggestort\b",
    r"\brefund\b",
    r"\bmoney\s+back\b",
    # Discount (requires human approval at Kinderuniversiteit)
    r"\bkorting\b",
    r"\bdiscount\b",
]

# Regex that extracts the [ESCALATE]…[/ESCALATE] block from AI output.
_ESCALATE_BLOCK_RE = re.compile(
    r"\[ESCALATE\](.*?)\[/ESCALATE\]",
    re.DOTALL | re.IGNORECASE,
)

# Holding-reply templates per language.
_HOLDING_NL = (
    "Bedankt voor je bericht over je betaling. "
    "Een van onze medewerkers bekijkt dit zo snel mogelijk en neemt contact met je op."
)
_HOLDING_EN = (
    "Thank you for your message about your payment. "
    "A member of our team will review this and get back to you as soon as possible."
)


# ── Engine ────────────────────────────────────────────────────────────────────


class EscalationRuleEngine:
    """Pure in-process rule engine — no I/O, no side effects."""

    def __init__(self, confidence_threshold: float | None = None) -> None:
        self._threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.escalation_confidence_threshold
        )
        self._payment_patterns = [
            re.compile(p, re.IGNORECASE) for p in _PAYMENT_STATUS_RAW
        ]
        self._financial_patterns = [
            re.compile(p, re.IGNORECASE) for p in _FINANCIAL_REQUEST_RAW
        ]

    # ── Pre-AI detection ──────────────────────────────────────────────────────

    def detect_from_message(self, text: str, language: str = "nl") -> EscalationDecision:
        """Run keyword rules on the raw user message before calling the AI.

        Payment-status matches return hold_reply=True so the caller can skip
        the AI entirely and return the canned holding message directly.

        Financial-request matches return hold_reply=False so the AI still
        responds (it knows the policy), but the conversation is escalated for
        human follow-up.
        """
        if any(p.search(text) for p in self._payment_patterns):
            holding = _HOLDING_NL if language == "nl" else _HOLDING_EN
            logger.debug("escalation_pre_ai_match", trigger="payment_status")
            return EscalationDecision(
                should_escalate=True,
                trigger=EscalationTrigger.PAYMENT_STATUS,
                reason=f"Payment status inquiry detected: {text[:120]}",
                urgency="high",
                hold_reply=True,
                human_message=holding,
            )

        if any(p.search(text) for p in self._financial_patterns):
            logger.debug("escalation_pre_ai_match", trigger="financial_request")
            return EscalationDecision(
                should_escalate=True,
                trigger=EscalationTrigger.FINANCIAL_REQUEST,
                reason=f"Financial information request detected: {text[:120]}",
                urgency="normal",
                hold_reply=False,
            )

        return EscalationDecision.no_escalation()

    # ── Post-AI detection ─────────────────────────────────────────────────────

    def detect_from_ai_response(self, ai_response: AIResponse) -> EscalationDecision:
        """Analyse the AI's output for escalation signals.

        Priority order:
          1. [ESCALATE] block — explicit, structured signal from the model
          2. requires_escalation flag on the AIResponse value object
          3. confidence_score below threshold
        """
        block_match = _ESCALATE_BLOCK_RE.search(ai_response.text)
        if block_match:
            reason, urgency, rule = _parse_escalate_block(block_match.group(1))
            trigger = _trigger_from_rule(rule)
            logger.debug("escalation_post_ai_block", trigger=trigger, urgency=urgency)
            return EscalationDecision(
                should_escalate=True,
                trigger=trigger,
                reason=reason or "AI signalled escalation via [ESCALATE] block",
                urgency=urgency,
                hold_reply=False,
            )

        if ai_response.requires_escalation:
            logger.debug("escalation_post_ai_flag")
            return EscalationDecision(
                should_escalate=True,
                trigger=EscalationTrigger.AI_SIGNAL,
                reason="AI response flagged requires_escalation=True",
                urgency="normal",
                hold_reply=False,
            )

        if ai_response.confidence_score < self._threshold:
            logger.debug(
                "escalation_low_confidence",
                score=ai_response.confidence_score,
                threshold=self._threshold,
            )
            return EscalationDecision(
                should_escalate=True,
                trigger=EscalationTrigger.LOW_CONFIDENCE,
                reason=(
                    f"AI confidence {ai_response.confidence_score:.2f} "
                    f"below threshold {self._threshold:.2f}"
                ),
                urgency="normal",
                hold_reply=False,
            )

        return EscalationDecision.no_escalation()

    # ── Text cleanup ──────────────────────────────────────────────────────────

    @staticmethod
    def strip_escalate_block(text: str) -> str:
        """Remove [ESCALATE]…[/ESCALATE] from AI output before sending to user."""
        return _ESCALATE_BLOCK_RE.sub("", text).strip()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_escalate_block(block: str) -> tuple[str, str, str]:
    """Extract reason, urgency, and rule from the text inside an [ESCALATE] block.

    Expected format (one key:value per line, any order):
        reason: Payment confirmation request
        rule: payment_status
        urgency: high
    """
    reason = ""
    urgency = "normal"
    rule = ""
    for line in block.strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "reason":
            reason = value
        elif key == "urgency" and value.lower() in ("high", "normal", "low"):
            urgency = value.lower()
        elif key == "rule":
            rule = value.lower()
    return reason, urgency, rule


def _trigger_from_rule(rule: str) -> EscalationTrigger:
    """Map the rule string from the [ESCALATE] block to an EscalationTrigger."""
    mapping = {
        "payment_status": EscalationTrigger.PAYMENT_STATUS,
        "financial_request": EscalationTrigger.FINANCIAL_REQUEST,
    }
    return mapping.get(rule, EscalationTrigger.AI_SIGNAL)
