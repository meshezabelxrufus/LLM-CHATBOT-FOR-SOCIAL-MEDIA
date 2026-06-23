"""Shared constants — no logic, no imports from within the app."""

# Supported messaging channels (mirrors ManyChat channel identifiers)
CHANNEL_FACEBOOK = "facebook"
CHANNEL_INSTAGRAM = "instagram"
CHANNEL_WHATSAPP = "whatsapp"
SUPPORTED_CHANNELS = {CHANNEL_FACEBOOK, CHANNEL_INSTAGRAM, CHANNEL_WHATSAPP}

# Conversation states
STATE_ACTIVE = "active"
STATE_ESCALATED = "escalated"
STATE_CLOSED = "closed"

# Message roles (OpenAI convention)
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"

# RAG
# paraphrase-multilingual-MiniLM-L12-v2 cosine similarity:
# English↔Dutch cross-lingual matches score ~0.30–0.55; same-language ~0.50–0.70.
# 0.30 passes clear semantic matches while rejecting unrelated chunks.
RAG_TOP_K = 5
RAG_SIMILARITY_THRESHOLD = 0.30

# Rate limiting
RATE_LIMIT_MESSAGES_PER_MINUTE = 20
