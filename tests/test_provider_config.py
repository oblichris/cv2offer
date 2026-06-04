from __future__ import annotations

from server.services.asr_service import get_asr_config
from server.services.llm_service import get_llm_config
from server.services.tts_service import get_tts_config


def test_provider_config_loads_mock_without_keys(isolated_env, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)

    assert get_llm_config()["mock"] is True
    assert get_asr_config()["mock"] is True
    assert get_tts_config()["mock"] is True
