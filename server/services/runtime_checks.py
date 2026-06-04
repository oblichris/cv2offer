from __future__ import annotations

import os
from typing import Any

from server.config import env_bool, load_environment


def provider_readiness() -> dict[str, Any]:
    load_environment()
    mock = env_bool("CV2OFFER_MOCK", False)
    return {
        "mock": mock,
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "deepseek"),
            "configured": mock or bool(os.getenv("DEEPSEEK_API_KEY")),
            "real_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "api_key_present": bool(os.getenv("DEEPSEEK_API_KEY")),
        },
        "asr": {
            "provider": os.getenv("ASR_PROVIDER", "stepfun"),
            "configured": mock or bool(os.getenv("STEPFUN_API_KEY")),
            "real_configured": bool(os.getenv("STEPFUN_API_KEY")),
            "api_key_present": bool(os.getenv("STEPFUN_API_KEY")),
        },
        "tts": {
            "provider": os.getenv("TTS_PROVIDER", "stepfun"),
            "configured": mock or bool(os.getenv("STEPFUN_API_KEY")),
            "real_configured": bool(os.getenv("STEPFUN_API_KEY")),
            "api_key_present": bool(os.getenv("STEPFUN_API_KEY")),
        },
    }


def audio_device_readiness(preferred_name: str | None = None) -> dict[str, Any]:
    preferred_name = preferred_name or os.getenv("COPILOT_AUDIO_DEVICE", "BlackHole")
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - depends on local PortAudio install.
        return {
            "configured": False,
            "preferred_name": preferred_name,
            "error": f"sounddevice unavailable: {exc}",
            "input_devices": [],
        }

    input_devices = []
    selected = None
    try:
        devices = sd.query_devices()
        for index, device in enumerate(devices):
            channels = int(device.get("max_input_channels", 0))
            if channels <= 0:
                continue
            item = {
                "index": index,
                "name": str(device.get("name", "")),
                "max_input_channels": channels,
                "default_samplerate": float(device.get("default_samplerate", 0)),
            }
            input_devices.append(item)
            if preferred_name.lower() in item["name"].lower():
                selected = item
    except Exception as exc:  # pragma: no cover - depends on host audio state.
        return {
            "configured": False,
            "preferred_name": preferred_name,
            "error": str(exc),
            "input_devices": input_devices,
        }

    return {
        "configured": selected is not None,
        "preferred_name": preferred_name,
        "selected": selected,
        "input_devices": input_devices,
    }


def runtime_readiness() -> dict[str, Any]:
    providers = provider_readiness()
    audio = audio_device_readiness()
    return {
        "providers": providers,
        "audio": audio,
        "ready_for_mock_demo": bool(providers["mock"]),
        "ready_for_real_interview_prep": bool(
            not providers["mock"]
            and providers["llm"]["real_configured"]
            and providers["asr"]["real_configured"]
            and providers["tts"]["real_configured"]
        ),
        "ready_for_real_copilot": bool(
            not providers["mock"]
            and providers["llm"]["real_configured"]
            and providers["asr"]["real_configured"]
            and audio["configured"]
        ),
    }
