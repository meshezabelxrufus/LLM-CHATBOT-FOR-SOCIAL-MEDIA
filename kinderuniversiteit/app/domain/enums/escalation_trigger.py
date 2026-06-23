from enum import StrEnum


class EscalationTrigger(StrEnum):
    PAYMENT_STATUS = "payment_status"
    FINANCIAL_REQUEST = "financial_request"
    AI_SIGNAL = "ai_signal"
    LOW_CONFIDENCE = "low_confidence"
