# api/telegram_router.py

import hashlib
import hmac
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response

from core.config import get_settings
from core.normalizer import normalize_chat_input
from core.orchestrator import run_agent
from core.models import Channel

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/telegram", tags=["Telegram"])

TELEGRAM_API = "https://api.telegram.org/bot"


async def send_telegram_message(chat_id: int | str, text: str) -> None:
    """Send a text reply back to the Telegram user."""
    _settings = get_settings()
    if not _settings.telegram_bot_token:
        logger.warning("telegram.no_token")
        return

    url = f"{TELEGRAM_API}{_settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("telegram.message_sent", chat_id=chat_id, text_length=len(text))
    except httpx.HTTPStatusError as e:
        logger.error("telegram.send_error", status=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        logger.error("telegram.request_error", error=str(e))


def _verify_secret(token: str | None) -> bool:
    """Verify the X-Telegram-Bot-Api-Secret-Token header matches our secret."""
    if not settings.telegram_webhook_secret:
        return True  # No secret configured, skip verification
    return hmac.compare_digest(
        token or "",
        settings.telegram_webhook_secret,
    )


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """
    Telegram webhook endpoint.
    Telegram POSTs every incoming message here.
    Flow:
      1. Verify secret token header.
      2. Extract chat_id, user_id, and message text.
      3. Run through agent pipeline.
      4. Send reply back to Telegram.
    """
    # Verify webhook secret
    if not _verify_secret(x_telegram_bot_api_secret_token):
        logger.warning("telegram.invalid_secret")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    body: dict[str, Any] = await request.json()
    logger.info("telegram.webhook_received", body_keys=list(body.keys()))

    # Extract message from update
    message = body.get("message") or body.get("edited_message")
    if not message:
        # Telegram sends other update types (callback_query, etc.) -- ignore them
        return Response(content="ok")

    chat_id = message.get("chat", {}).get("id")
    user_id = str(message.get("from", {}).get("id", "unknown"))
    username = message.get("from", {}).get("username", "")
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return Response(content="ok")

    log = logger.bind(chat_id=chat_id, user_id=user_id, username=username)
    log.info("telegram.message_received", text_preview=text[:80])

    # Normalize into standard message format
    session_id = f"tg_{user_id}"
    normalized = normalize_chat_input(
        raw_text=text,
        channel=Channel.TELEGRAM,
        customer_phone=f"tg_{user_id}",
        session_id=session_id,
    )

    # Run agent pipeline
    try:
        result = await run_agent(normalized)
        agent_reply: str = result.get("response_text", "")

        if not agent_reply:
            agent_reply = "I am sorry, I could not process that. Could you please try again?"

        await send_telegram_message(chat_id, agent_reply)
        log.info("telegram.reply_sent", reply_preview=agent_reply[:80])

    except Exception as exc:
        log.error("telegram.pipeline_error", error=str(exc), exc_info=True)
        await send_telegram_message(
            chat_id,
            "I am sorry, something went wrong. Please try again in a moment.",
        )

    return Response(content="ok")


@router.get("/test")
async def telegram_test() -> dict:
    """Health check for the Telegram router."""
    return {
        "status": "ok",
        "router": "telegram",
        "bot_token_configured": bool(settings.telegram_bot_token),
        "webhook_secret_configured": bool(settings.telegram_webhook_secret),
    }