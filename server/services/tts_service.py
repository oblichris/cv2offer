from __future__ import annotations

import os
import wave
from io import BytesIO

import httpx
from server.config import env_bool, load_environment
from server.services.llm_service import ProviderConfigError


def get_tts_config() -> dict[str, str | bool]:
    load_environment()
    provider = os.getenv("TTS_PROVIDER", "stepfun")
    mock = env_bool("CV2OFFER_MOCK", False)
    api_key = os.getenv("STEPFUN_API_KEY", "")
    if not mock and provider == "stepfun" and not api_key:
        raise ProviderConfigError("Missing STEPFUN_API_KEY. Set CV2OFFER_MOCK=1 for mock mode.")
    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.com/v1"),
        "model": os.getenv("STEPFUN_TTS_MODEL", "stepaudio-2.5-tts"),
        "voice": os.getenv("STEPFUN_TTS_VOICE", "tianmeinvsheng"),
        "mock": mock,
    }


def synthesize_speech(text: str) -> bytes:
    config = get_tts_config()
    if config["mock"]:
        return mock_wav_bytes()
    response = httpx.post(
        f"{config['base_url']}/audio/speech",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "voice": config["voice"],
            "input": text[:1000],
            "response_format": "mp3",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def mock_wav_bytes() -> bytes:
    buffer = BytesIO()
    sample_rate = 16000
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(sample_rate * 0.15))
    return buffer.getvalue()
