"""
Bidirectional mapping between SQLAlchemy ORM models and pure domain entities.

Rules:
- Mappers are pure functions — no I/O, no side effects.
- ORM models never leave the infrastructure layer; domain entities never
  import from infrastructure. Mappers are the only bridge.
- The `metadata_` column name (underscore avoids shadowing SQLAlchemy's
  internal `metadata` attribute) maps to `metadata` on the domain entity.
"""
from app.domain.entities.contact import Contact
from app.domain.entities.conversation import Conversation
from app.domain.entities.escalation import Escalation
from app.domain.entities.message import Message
from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState
from app.domain.enums.message_role import MessageRole
from app.infrastructure.database.models.contact_model import ContactModel
from app.infrastructure.database.models.conversation_model import ConversationModel
from app.infrastructure.database.models.escalation_model import EscalationModel
from app.infrastructure.database.models.message_model import MessageModel


# ── Conversation ──────────────────────────────────────────────────────────────


def conversation_to_domain(model: ConversationModel) -> Conversation:
    return Conversation(
        id=model.id,
        contact_id=model.contact_id,
        channel=Channel(model.channel),
        state=ConversationState(model.state),
        language=model.language,
        last_interaction_at=model.last_interaction_at,
        metadata=model.metadata_ or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def conversation_from_domain(entity: Conversation) -> ConversationModel:
    return ConversationModel(
        id=entity.id,
        contact_id=entity.contact_id,
        channel=entity.channel.value,
        state=entity.state.value,
        language=entity.language,
        last_interaction_at=entity.last_interaction_at,
        metadata_=entity.metadata,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


# ── Message ───────────────────────────────────────────────────────────────────


def message_to_domain(model: MessageModel) -> Message:
    return Message(
        id=model.id,
        conversation_id=model.conversation_id,
        role=MessageRole(model.role),
        content=model.content,
        tokens_used=model.tokens_used,
        confidence_score=model.confidence_score,
        metadata=model.metadata_ or {},
        created_at=model.created_at,
    )


def message_from_domain(entity: Message) -> MessageModel:
    return MessageModel(
        id=entity.id,
        conversation_id=entity.conversation_id,
        role=entity.role.value,
        content=entity.content,
        tokens_used=entity.tokens_used,
        confidence_score=entity.confidence_score,
        metadata_=entity.metadata,
        created_at=entity.created_at,
    )


# ── Contact ───────────────────────────────────────────────────────────────────


def contact_to_domain(model: ContactModel) -> Contact:
    return Contact(
        id=model.id,
        external_id=model.external_id,
        channel=Channel(model.channel),
        display_name=model.display_name,
        locale=model.locale,
        last_seen_at=model.last_seen_at,
        metadata=model.metadata_ or {},
        created_at=model.created_at,
    )


def contact_from_domain(entity: Contact) -> ContactModel:
    return ContactModel(
        id=entity.id,
        external_id=entity.external_id,
        channel=entity.channel.value,
        display_name=entity.display_name,
        locale=entity.locale,
        last_seen_at=entity.last_seen_at,
        metadata_=entity.metadata,
        created_at=entity.created_at,
    )


# ── Escalation ────────────────────────────────────────────────────────────────


def escalation_to_domain(model: EscalationModel) -> Escalation:
    return Escalation(
        id=model.id,
        conversation_id=model.conversation_id,
        reason=model.reason,
        resolved=model.resolved,
        agent_id=model.agent_id,
        notes=model.notes,
        created_at=model.created_at,
        resolved_at=model.resolved_at,
    )


def escalation_from_domain(entity: Escalation) -> EscalationModel:
    return EscalationModel(
        id=entity.id,
        conversation_id=entity.conversation_id,
        reason=entity.reason,
        resolved=entity.resolved,
        agent_id=entity.agent_id,
        notes=entity.notes,
        created_at=entity.created_at,
        resolved_at=entity.resolved_at,
    )
