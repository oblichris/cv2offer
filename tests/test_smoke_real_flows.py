from __future__ import annotations

import pytest

from scripts.smoke_real_flows import ensure_real_ready


def test_real_smoke_gate_fails_without_provider_keys(isolated_env, monkeypatch):
    monkeypatch.setenv("CV2OFFER_MOCK", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("STEPFUN_API_KEY", "")

    with pytest.raises(RuntimeError, match="Real interview prep is not ready"):
        ensure_real_ready("interview-prep")
