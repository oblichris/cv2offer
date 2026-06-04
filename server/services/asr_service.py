from __future__ import annotations

import os
import json
from typing import Any

import httpx
from server.config import env_bool, load_environment
from server.services.llm_service import ProviderConfigError


def get_asr_config() -> dict[str, str | bool]:
    load_environment()
    provider = os.getenv("ASR_PROVIDER", "stepfun")
    mock = env_bool("CV2OFFER_MOCK", False)
    api_key = os.getenv("STEPFUN_API_KEY", "")
    if not mock and provider == "stepfun" and not api_key:
        raise ProviderConfigError("Missing STEPFUN_API_KEY. Set CV2OFFER_MOCK=1 for mock mode.")
    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.com/v1"),
        "model": os.getenv("STEPFUN_ASR_MODEL", "stepaudio-2.5-asr"),
        "stream_model": os.getenv("STEPFUN_STREAM_ASR_MODEL", "stepaudio-2.5-asr"),
        "mock": mock,
    }


def mime_to_format(mime_type: str) -> dict[str, Any]:
    lower = (mime_type or "").lower()
    if "ogg" in lower:
        return {"type": "ogg"}
    if "mp3" in lower or "mpeg" in lower:
        return {"type": "mp3"}
    if "wav" in lower or "wave" in lower:
        return {"type": "wav"}
    return {"type": "wav"}


def transcribe_audio_base64(audio_base64: str, mime_type: str = "audio/wav", language: str = "zh") -> str:
    config = get_asr_config()
    if config["mock"]:
        return "这是 mock ASR 转写：我会结合咨询经验和 AI 工作流能力回答这个问题。"
    response_text = ""
    with httpx.stream(
        "POST",
        f"{config['base_url']}/audio/asr/sse",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json={
            "audio": {
                "data": audio_base64,
                "input": {
                    "transcription": {
                        "model": config["model"],
                        "language": language,
                        "enable_itn": True,
                    },
                    "format": mime_to_format(mime_type),
                },
            }
        },
        timeout=120,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            event_type = payload.get("type") or payload.get("event")
            text = payload.get("text") or payload.get("delta") or payload.get("transcript", "")
            if text:
                response_text += text
            if event_type == "transcript.text.done":
                break
    return response_text.strip()
