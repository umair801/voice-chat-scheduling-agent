# tests/test_sales_agent.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from core.models import NormalizedMessage, Channel, Intent, ParsedIntent, ExtractedEntities


def make_message(text: str, channel: Channel = Channel.CHAT) -> NormalizedMessage:
    return NormalizedMessage(
        session_id="test-sales-001",
        channel=channel,
        raw_text=text,
        customer_phone="+1234567890",
        timestamp=datetime.utcnow(),
    )


def make_mock_parsed_intent(intent: Intent, confidence: float = 0.95) -> ParsedIntent:
    """Helper to build a ParsedIntent for mocking."""
    return ParsedIntent(
        intent=intent,
        confidence=confidence,
        entities=ExtractedEntities(
            service_type=None,
            preferred_date=None,
            preferred_time=None,
            location=None,
            customer_name="Test Customer",
            customer_email="test@example.com",
        ),
        raw_response="mocked",
        session_id="test-sales-001",
    )


class TestSalesAgentModels:
    """Test that sales-related models and enums are correctly defined."""

    def test_sales_inquiry_intent_exists(self):
        assert Intent.SALES_INQUIRY in Intent.__members__.values()

    def test_pricing_question_intent_exists(self):
        assert Intent.PRICING_QUESTION in Intent.__members__.values()

    def test_demo_request_intent_exists(self):
        assert Intent.DEMO_REQUEST in Intent.__members__.values()

    def test_callback_request_intent_exists(self):
        assert Intent.CALLBACK_REQUEST in Intent.__members__.values()

    def test_parsed_intent_creation_sales(self):
        intent = make_mock_parsed_intent(Intent.SALES_INQUIRY)
        assert intent.intent == Intent.SALES_INQUIRY
        assert intent.confidence == 0.95
        assert intent.entities.customer_name == "Test Customer"

    def test_parsed_intent_creation_pricing(self):
        intent = make_mock_parsed_intent(Intent.PRICING_QUESTION, confidence=0.88)
        assert intent.intent == Intent.PRICING_QUESTION
        assert intent.confidence == 0.88

    def test_parsed_intent_creation_demo(self):
        intent = make_mock_parsed_intent(Intent.DEMO_REQUEST)
        assert intent.intent == Intent.DEMO_REQUEST


class TestSalesAgentImport:
    """Test that the sales agent imports cleanly."""

    def test_sales_agent_imports(self):
        try:
            from agents.sales_agent import parse_sales_intent
            assert callable(parse_sales_intent)
        except ImportError as e:
            pytest.fail(f"Sales agent import failed: {e}")

    def test_sales_agent_function_is_async(self):
        import asyncio
        from agents.sales_agent import parse_sales_intent
        assert asyncio.iscoroutinefunction(parse_sales_intent)


class TestSalesMessageNormalization:
    """Test that sales messages normalize correctly."""

    def test_sales_message_via_chat(self):
        msg = make_message("I'm interested in your satellite services pricing")
        assert msg.channel == Channel.CHAT
        assert "pricing" in msg.raw_text.lower()

    def test_sales_message_via_voice(self):
        msg = make_message("Can I get a demo of your system", Channel.VOICE)
        assert msg.channel == Channel.VOICE

    def test_sales_message_via_telegram(self):
        msg = make_message("Tell me about your plans", Channel.TELEGRAM)
        assert msg.channel == Channel.TELEGRAM

    def test_sales_message_preserves_session(self):
        msg = make_message("I need pricing information")
        assert msg.session_id == "test-sales-001"
        assert msg.customer_phone == "+1234567890"