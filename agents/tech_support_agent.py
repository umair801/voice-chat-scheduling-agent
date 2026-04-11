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
from core.knowledge_base import KnowledgeBase
from agents.rag_retriever import RAGRetriever
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = genai.Client(api_key=settings.gemini_api_key)

# Initialize KB and RAG once
_kb = KnowledgeBase()
_rag = RAGRetriever(_kb)

_TECH_SUPPORT_SYSTEM_PROMPT = """You are a technical support agent for a satellite services company.

{kb_context}

Analyze this customer message and classify it. Return ONLY valid JSON with no markdown:

{{
  "intent": "tech_inquiry|unknown",
  "confidence": 0.95,
  "entities": {{
    "issue_type": "connectivity|account|billing|service|other",
    "urgency": "low|medium|high",
    "notes": "brief issue summary"
  }}
}}
"""


async def parse_tech_intent(message: NormalizedMessage) -> ParsedIntent:
    """
    Classify a message as a technical support inquiry with RAG context.
    Returns ParsedIntent with tech support-specific intent values.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Retrieve context from knowledge base
    context_data = _rag.retrieve_context(
        query=message.raw_text,
        top_k=3,
        min_similarity=0.5
    )
    
    # Format context for prompt
    kb_context = _rag.format_context_for_prompt(context_data)
    if not kb_context:
        kb_context = "No similar past issues found in knowledge base. Provide your best technical guidance."
    
    prompt = _TECH_SUPPORT_SYSTEM_PROMPT.format(kb_context=kb_context)
    user_content = f"Customer message: {message.raw_text}"

    logger.info(
        "tech_support_agent.start",
        session_id=message.session_id,
        channel=message.channel.value,
        text=message.raw_text[:100],
        kb_context_found=context_data["found_context"],
    )

    try:
        response = await _call_gemini_async(prompt, user_content)
        parsed = _parse_tech_response(response, message)

        logger.info(
            "tech_support_agent.success",
            session_id=message.session_id,
            intent=parsed.intent.value,
            confidence=parsed.confidence,
            kb_confidence=context_data["confidence"],
        )

        return parsed

    except Exception as e:
        logger.error(
            "tech_support_agent.failed",
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
    full_prompt = f"{system_prompt}\n\nCustomer: {user_content}"

    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _client.models.generate_content(
                    model=settings.gemini_model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
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


def _parse_tech_response(response: str, message: NormalizedMessage) -> ParsedIntent:
    """Parse Gemini response and return ParsedIntent."""
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
        
        # Fix truncated string values (e.g. "notes": "some text without closing quote)
        json_str = re.sub(r'("[\w_]+":\s*"[^"]*?)([,}\n])', lambda m: m.group(1) + '"' + m.group(2) if not m.group(1).endswith('"') else m.group(0), json_str)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Last resort: extract only the top-level fields we need via regex
            intent_match = re.search(r'"intent"\s*:\s*"([^"]+)"', cleaned)
            conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', cleaned)
            data = {
                "intent": intent_match.group(1) if intent_match else "unknown",
                "confidence": conf_match.group(1) if conf_match else "0.0",
                "entities": {},
            }

        # Map string intent to Intent enum
        intent_map = {
            "tech_inquiry": Intent.TECH_INQUIRY,
            "account_issue": Intent.TECH_INQUIRY,
            "service_problem": Intent.TECH_INQUIRY,
            "billing_question": Intent.TECH_INQUIRY,
            "general_inquiry": Intent.GENERAL_INQUIRY,
            "unknown": Intent.UNKNOWN,
        }

        intent_str = data.get("intent", "unknown").lower()
        intent = intent_map.get(intent_str, Intent.UNKNOWN)
        confidence = float(data.get("confidence", 0.0))

        # Extract entities
        entities_data = data.get("entities", {})
        entities = ExtractedEntities(
            notes=entities_data.get("notes"),
            urgency=entities_data.get("urgency"),
        )

        return ParsedIntent(
            intent=intent,
            confidence=confidence,
            entities=entities,
            raw_response=response,
        )

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("tech_support_agent.parse_error", error=str(e), response=response)
        return ParsedIntent(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            entities=ExtractedEntities(),
            raw_response=response,
        )
    