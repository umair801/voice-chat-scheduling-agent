# tests/test_tech_support_agent.py

import pytest
import asyncio
from datetime import datetime

from core.models import NormalizedMessage, Channel, Intent, ParsedIntent, ExtractedEntities


def make_message(text: str, channel: Channel = Channel.CHAT) -> NormalizedMessage:
    return NormalizedMessage(
        session_id="test-tech-001",
        channel=channel,
        raw_text=text,
        customer_phone="+1234567890",
        timestamp=datetime.utcnow(),
    )


def make_mock_parsed_intent(intent: Intent, confidence: float = 0.95) -> ParsedIntent:
    return ParsedIntent(
        intent=intent,
        confidence=confidence,
        entities=ExtractedEntities(
            service_type=None,
            preferred_date=None,
            preferred_time=None,
            location=None,
            customer_name=None,
            customer_email=None,
        ),
        raw_response="mocked",
        session_id="test-tech-001",
    )


class TestTechSupportModels:
    """Test that tech support intents are defined correctly."""

    def test_tech_inquiry_intent_exists(self):
        assert Intent.TECH_INQUIRY in Intent.__members__.values()

    def test_tech_inquiry_intent_value(self):
        assert Intent.TECH_INQUIRY.value == "tech_inquiry"

    def test_parsed_intent_tech_creation(self):
        intent = make_mock_parsed_intent(Intent.TECH_INQUIRY)
        assert intent.intent == Intent.TECH_INQUIRY
        assert intent.confidence == 0.95

    def test_parsed_intent_high_confidence(self):
        intent = make_mock_parsed_intent(Intent.TECH_INQUIRY, confidence=0.98)
        assert intent.confidence >= 0.95

    def test_parsed_intent_low_confidence(self):
        intent = make_mock_parsed_intent(Intent.UNKNOWN, confidence=0.3)
        assert intent.intent == Intent.UNKNOWN
        assert intent.confidence < 0.5


class TestTechSupportAgentImport:
    """Test that the tech support agent imports cleanly."""

    def test_tech_support_agent_imports(self):
        try:
            from agents.tech_support_agent import parse_tech_intent
            assert callable(parse_tech_intent)
        except ImportError as e:
            pytest.fail(f"Tech support agent import failed: {e}")

    def test_tech_support_agent_is_async(self):
        from agents.tech_support_agent import parse_tech_intent
        assert asyncio.iscoroutinefunction(parse_tech_intent)


class TestTechSupportMessageNormalization:
    """Test tech support message normalization across channels."""

    def test_tech_message_via_chat(self):
        msg = make_message("My satellite dish is not connecting")
        assert msg.channel == Channel.CHAT
        assert "satellite" in msg.raw_text.lower()

    def test_tech_message_via_voice(self):
        msg = make_message("I have no signal on my receiver", Channel.VOICE)
        assert msg.channel == Channel.VOICE

    def test_tech_message_via_telegram(self):
        msg = make_message("Error code E101 on my device", Channel.TELEGRAM)
        assert msg.channel == Channel.TELEGRAM
        assert msg.session_id == "test-tech-001"

    def test_tech_message_empty_entities(self):
        intent = make_mock_parsed_intent(Intent.TECH_INQUIRY)
        assert intent.entities.service_type is None
        assert intent.entities.preferred_date is None

    def test_tech_message_session_preserved(self):
        msg = make_message("My internet keeps dropping")
        assert msg.session_id == "test-tech-001"
        assert msg.customer_phone == "+1234567890"