# api/voice_router.py

import uuid
import base64
from typing import Optional

import structlog
from fastapi import APIRouter, Form, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather, Play

from core.normalizer import normalize_voice_input
from core.orchestrator import run_agent
from core.session_manager import close_session
from notifications.elevenlabs_tts import synthesize_speech

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])

# In-memory store for temporary audio clips (keyed by clip ID)
_audio_cache: dict[str, bytes] = {}


async def _build_twiml(
    message: str,
    request: Request,
    gather: bool = True,
) -> str:
    """
    Build TwiML response. Uses ElevenLabs audio via <Play> if synthesis
    succeeds, falls back to Polly <Say> if ElevenLabs returns empty bytes.
    """
    vr = VoiceResponse()

    # Attempt ElevenLabs synthesis
    audio_bytes = await synthesize_speech(message)

    if audio_bytes:
        # Store audio in cache and build a URL Twilio can fetch
        clip_id = uuid.uuid4().hex
        _audio_cache[clip_id] = audio_bytes
        base_url = str(request.base_url).rstrip("/")
        audio_url = f"{base_url}/voice/audio/{clip_id}"

        if gather:
            g = Gather(
                input="speech",
                action="/voice/webhook",
                method="POST",
                speech_timeout="auto",
                language="en-US",
            )
            g.play(audio_url)
            vr.append(g)
            vr.say(
                "I did not hear anything. Please call back if you need assistance.",
                voice="Polly.Joanna",
            )
        else:
            vr.play(audio_url)
            vr.hangup()

    else:
        # Fallback: Polly TTS
        if gather:
            g = Gather(
                input="speech",
                action="/voice/webhook",
                method="POST",
                speech_timeout="auto",
                language="en-US",
            )
            g.say(message, voice="Polly.Joanna", language="en-US")
            vr.append(g)
            vr.say(
                "I did not hear anything. Please call back if you need assistance.",
                voice="Polly.Joanna",
            )
        else:
            vr.say(message, voice="Polly.Joanna", language="en-US")
            vr.hangup()

    return str(vr)


def _is_terminal_response(agent_reply: str) -> bool:
    terminal_phrases = [
        "your appointment is confirmed",
        "booking has been cancelled",
        "have a great day",
        "goodbye",
        "thank you for calling",
        "we will see you",
    ]
    lower = agent_reply.lower()
    return any(phrase in lower for phrase in terminal_phrases)


@router.get("/audio/{clip_id}")
async def serve_audio(clip_id: str) -> Response:
    """
    Serve a temporary ElevenLabs audio clip to Twilio.
    Clips are stored in memory and served once.
    """
    audio = _audio_cache.pop(clip_id, None)
    if not audio:
        return Response(status_code=404)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/webhook")
async def voice_webhook(
    request: Request,
    CallSid: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    SpeechResult: Optional[str] = Form(None),
    CallStatus: Optional[str] = Form(None),
) -> Response:
    call_sid = CallSid or f"test-{uuid.uuid4().hex[:8]}"
    caller_number = From or "unknown"
    speech_text = SpeechResult or ""

    log = logger.bind(call_sid=call_sid, caller=caller_number)
    log.info("voice_webhook_received", speech=speech_text, call_status=CallStatus)

    if CallStatus in ("completed", "busy", "no-answer", "failed", "canceled"):
        log.info("call_ended", status=CallStatus)
        await close_session(call_sid)
        return Response(content="", media_type="application/xml")

    if not speech_text:
        greeting = (
            "Hello! Thank you for calling. I am your AI scheduling assistant. "
            "How can I help you today? You can book an appointment, reschedule, "
            "or cancel an existing booking."
        )
        twiml = await _build_twiml(greeting, request, gather=True)
        log.info("voice_greeting_sent")
        return Response(content=twiml, media_type="application/xml")

    try:
        normalized = normalize_voice_input(
            raw_text=speech_text,
            call_sid=call_sid,
            caller_number=caller_number,
        )

        result = await run_agent(normalized)
        agent_reply: str = result.get("response_text", "")

        if not agent_reply:
            agent_reply = (
                "I am sorry, I could not process that. Could you please repeat?"
            )

        terminal = _is_terminal_response(agent_reply)
        twiml = await _build_twiml(agent_reply, request, gather=not terminal)

        log.info(
            "voice_reply_sent",
            reply_preview=agent_reply[:80],
            terminal=terminal,
        )
        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        log.error("voice_webhook_error", error=str(exc), exc_info=True)
        fallback = (
            "I am sorry, something went wrong on my end. "
            "Please try again or call back in a moment."
        )
        twiml = await _build_twiml(fallback, request, gather=False)
        return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def voice_status_callback(
    CallSid: Optional[str] = Form(None),
    CallStatus: Optional[str] = Form(None),
) -> Response:
    log = logger.bind(call_sid=CallSid)
    log.info("voice_status_callback", status=CallStatus)

    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        if CallSid:
            await close_session(CallSid)
            log.info("session_cleaned_up", call_sid=CallSid)

    return Response(content="", media_type="application/xml")


@router.get("/test")
async def voice_test_endpoint() -> dict:
    sample_twiml = VoiceResponse()
    sample_twiml.say("Voice router is online. Agent pipeline is ready.", voice="Polly.Joanna")
    return {
        "status": "ok",
        "router": "voice",
        "sample_twiml": str(sample_twiml),
    }