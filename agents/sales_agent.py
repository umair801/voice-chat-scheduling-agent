import json
import re
import asyncio
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types

from core.config import get_settings
from core.models import (
    NormalizedMessage,
    ParsedIntent,
    ExtractedEntities,
    Intent,
)
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = genai.Client(api_key=settings.gemini_api_key)

_SALES_SYSTEM_PROMPT = """You are a sales intake agent for a satellite services company.

Your job is to analyze a customer message and determine if it's a sales inquiry. If it is, extract structured data for the sales team.

Return a JSON object with exactly this structure:

{{
  "intent": "<one of: sales_inquiry, callback_request, pricing_question, demo_request, general_inquiry, or unknown>",
  "confidence": <float between 0.0 and 1.0>,
  "is_sales": <true if this is sales-related, false otherwise>,
  "entities": {{
    "customer_name": "<name if mentioned, otherwise null>",
    "customer_email": "<email if mentioned, otherwise null>",
    "company_name": "<company or business name if mentioned, otherwise null>",
    "inquiry_type": "<pricing, demo, information, callback, or other>",
    "urgency": "<low, medium, high based on tone and context>",
    "notes": "<summary of what the customer is asking or needs>",
    "preferred_callback_time": "<time preference if mentioned, otherwise null>"
  }}
}}

Rules:
- Return ONLY valid JSON. No markdown, no explanation, no preamble.
- If the customer is asking about pricing, features, demos, or general information, it's a sales inquiry.
- If they're asking to schedule a service appointment, it's NOT a sales inquiry (return is_sales: false).
- Extract any personal details mentioned (name, email, company).
- Urgency should be inferred from tone: "ASAP" or "urgent" = high, "when you get a chance" = low, otherwise medium.
- Confidence below 0.5 means intent is "unknown".
"""


async def parse_sales_intent(message: NormalizedMessage) -> ParsedIntent:
    """
    Classify a message as a sales inquiry and extract relevant entities.
    Returns ParsedIntent with sales-specific intent values.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    prompt = _SALES_SYSTEM_PROMPT
    user_content = f"Customer message: {message.raw_text}"

    logger.info(
        "sales_agent.start",
        session_id=message.session_id,
        channel=message.channel.value,
        text=message.raw_text[:100],
    )

    try:
        response = await _call_gemini_async(prompt, user_content)
        parsed = _parse_sales_response(response, message)

        logger.info(
            "sales_agent.success",
            session_id=message.session_id,
            intent=parsed.intent.value,
            confidence=parsed.confidence,
        )

        return parsed

    except Exception as e:
        logger.error(
            "sales_agent.failed",
            session_id=message.session_id,
            error=str(e),
        )
        return ParsedIntent(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            entities=ExtractedEntities(),
            raw_response=str(e),
        )


async def _call_gemini_async(system_prompt: str, user_content: str) -> str:
    """Async Gemini call with manual retry logic."""
    max_retries = 3
    wait_time = 1.0
    full_prompt = f"{system_prompt}\n\n{user_content}"

    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _client.models.generate_content(
                    model=settings.gemini_model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        top_p=0.9,
                        top_k=40,
                        max_output_tokens=500,
                    ),
                ),
            )
            return response.text

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "gemini_call.retry",
                    attempt=attempt + 1,
                    error=str(e),
                    wait_seconds=wait_time,
                )
                await asyncio.sleep(wait_time)
                wait_time *= 2  # exponential backoff
            else:
                logger.error("gemini_call.failed_all_retries", error=str(e))
                raise


def _parse_sales_response(response: str, message: NormalizedMessage) -> ParsedIntent:
    """Parse Gemini response and return ParsedIntent."""
    try:
        # Clean up response (remove markdown code blocks if present)
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", response).strip()
        
        # Fix incomplete floats like "1." -> "1.0"
        cleaned = re.sub(r':\s*(\d+)\.([,\n}])', r': \1.0\2', cleaned)
        
        data = json.loads(cleaned)

        # Map string intent to Intent enum
        intent_map = {
            "sales_inquiry": Intent.SALES_INQUIRY,
            "callback_request": Intent.CALLBACK_REQUEST,
            "pricing_question": Intent.PRICING_QUESTION,
            "demo_request": Intent.DEMO_REQUEST,
            "general_inquiry": Intent.GENERAL_INQUIRY,
            "unknown": Intent.UNKNOWN,
        }

        intent_str = data.get("intent", "unknown").lower()
        intent = intent_map.get(intent_str, Intent.UNKNOWN)
        confidence = float(data.get("confidence", 0.0))

        # Extract entities
        entities_data = data.get("entities", {})
        entities = ExtractedEntities(
            customer_name=entities_data.get("customer_name"),
            customer_email=entities_data.get("customer_email"),
            company_name=entities_data.get("company_name"),
            inquiry_type=entities_data.get("inquiry_type"),
            urgency=entities_data.get("urgency"),
            notes=entities_data.get("notes"),
            preferred_callback_time=entities_data.get("preferred_callback_time"),
        )

        return ParsedIntent(
            intent=intent,
            confidence=confidence,
            entities=entities,
            raw_response=response,
        )

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("sales_agent.parse_error", error=str(e), response=response)
        return ParsedIntent(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            entities=ExtractedEntities(),
            raw_response=response,
        )