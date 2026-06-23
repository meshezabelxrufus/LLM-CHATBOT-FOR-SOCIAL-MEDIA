"""Unit tests for the Conversation domain entity."""
import pytest
from app.domain.entities.conversation import Conversation
from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState


def test_conversation_defaults_to_active_state():
    conv = Conversation(contact_id="abc123", channel=Channel.WHATSAPP)
    assert conv.state == ConversationState.ACTIVE


def test_conversation_has_unique_id():
    c1 = Conversation(contact_id="a", channel=Channel.FACEBOOK)
    c2 = Conversation(contact_id="a", channel=Channel.FACEBOOK)
    assert c1.id != c2.id
