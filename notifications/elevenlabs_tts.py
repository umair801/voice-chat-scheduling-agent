import httpx
from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def synthesize_speech(text: str) -> bytes:
    """
    Convert text to speech using ElevenLabs API.
    Returns raw MP3 audio bytes.
    Falls back to empty bytes on failure so Twilio can still respond.
    """
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_tts.no_api_key", text_length=len(text))
        return b""

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"

    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(
                "elevenlabs_tts.success",
                text_length=len(text),
                audio_bytes=len(response.content),
            )
            return response.content

    except httpx.HTTPStatusError as e:
        logger.error(
            "elevenlabs_tts.http_error",
            status_code=e.response.status_code,
            detail=e.response.text,
        )
        return b""

    except httpx.RequestError as e:
        logger.error("elevenlabs_tts.request_error", error=str(e))
        return b""