from __future__ import annotations

import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from server.app import app
from server.services.runtime_checks import audio_device_readiness, provider_readiness


def test_provider_readiness_respects_mock_mode(isolated_env, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("STEPFUN_API_KEY", "")
    readiness = provider_readiness()

    assert readiness["mock"] is True
    assert readiness["llm"]["configured"] is True
    assert readiness["llm"]["real_configured"] is False
    assert readiness["asr"]["configured"] is True
    assert readiness["tts"]["configured"] is True
    assert readiness["llm"]["api_key_present"] is False


def test_audio_device_readiness_selects_blackhole(monkeypatch):
    fake_sounddevice = SimpleNamespace(
        query_devices=lambda: [
            {"name": "MacBook Microphone", "max_input_channels": 1, "default_samplerate": 48000},
            {"name": "BlackHole 2ch", "max_input_channels": 2, "default_samplerate": 48000},
        ]
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)

    readiness = audio_device_readiness("BlackHole")

    assert readiness["configured"] is True
    assert readiness["selected"]["name"] == "BlackHole 2ch"


def test_runtime_checks_endpoint(isolated_env):
    with TestClient(app) as client:
        response = client.get("/api/runtime/checks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"]["mock"] is True
    assert payload["ready_for_mock_demo"] is True
    assert payload["ready_for_real_interview_prep"] is False
