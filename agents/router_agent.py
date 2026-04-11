import json
import re
import asyncio
from datetime import datetime
from typing import Optional, Literal

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

_ROUTER_SYSTEM_PROMPT = """You are an intent router for a satellite services company.

Analyze the customer message and determine if it's a SALES inquiry or a TECHNICAL SUPPORT inquiry.

Return ONLY a valid JSON object:

{
  "category": "sales|technical|unknown",
  "confidence": 0.95,
  "reasoning": "brief reason for the classification"
}

Rules:
- Return ONLY valid JSON. No markdown, no backticks, no explanation.
- SALES: pricing, demos, features, callbacks, general information, upgrades
- TECHNICAL: connectivity issues, service problems, billing disputes, account issues, troubleshooting
- If unclear, return "unknown"
- Do not use incomplete floats. Use 0.95 not 0.
"""


async def route_intent(message: NormalizedMessage) -> Literal["sales", "technical", "unknown"]:
    """
    Classify a message into sales or technical support category.
    Returns the routing category as a string.
    """
    prompt = _ROUTER_SYSTEM_PROMPT
    user_content = f"Customer message: {message.raw_text}"

    logger.info(
        "router_agent.start",
        session_id=message.session_id,
        channel=message.channel.value,
        text=message.raw_text[:100],
    )

    try:
        response = await _call_gemini_async(prompt, user_content)
        category = _parse_router_response(response)

        logger.info(
            "router_agent.success",
            session_id=message.session_id,
            category=category,
        )

        return category

    except Exception as e:
        logger.error(
            "router_agent.failed",
            session_id=message.session_id,
            error=str(e),
        )
        return "unknown"


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
                        temperature=0.1,  # Lower temperature for routing decision
                        max_output_tokens=300,  # Enough for complete JSON
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
                wait_time *= 2
            else:
                logger.error("gemini_call.failed_all_retries", error=str(e))
                raise


def _parse_router_response(response: str) -> Literal["sales", "technical", "unknown"]:
    """Parse Gemini response and return routing category."""
    try:
        # Clean up response
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", response).strip()
        
        # Find JSON object using bracket counting
        start_idx = cleaned.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found")
        
        # Find matching closing brace
        bracket_count = 0
        in_string = False
        escape_next = False
        end_idx = -1
        
        for i in range(start_idx, len(cleaned)):
            char = cleaned[i]
            
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i
                        break
        
        # Extract JSON string
        if end_idx == -1:
            if bracket_count > 0:
                json_str = cleaned[start_idx:] + "}" * bracket_count
            else:
                raise ValueError("No matching closing brace")
        else:
            json_str = cleaned[start_idx:end_idx+1]
        
        # Fix incomplete floats
        json_str = re.sub(r':\s*(\d+)\.([,\n\s}])', r': \1.0\2', json_str)
        
        data = json.loads(json_str)
        
        category = data.get("category", "unknown").lower()
        
        # Validate category
        if category not in ["sales", "technical", "unknown"]:
            logger.warning("router_agent.invalid_category", category=category)
            return "unknown"
        
        return category

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("router_agent.parse_error", error=str(e), response=response)
        return "unknown"
    
    