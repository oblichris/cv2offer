from __future__ import annotations

from pathlib import Path

import pytest

from server.config import get_settings


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    context_dir = tmp_path / "context"
    output_dir = tmp_path / "outputs"
    db_path = tmp_path / "db" / "cv2offer.sqlite"
    monkeypatch.setenv("CV2OFFER_MOCK", "1")
    monkeypatch.setenv("CONTEXT_DIR", str(context_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CV2OFFER_DB_PATH", str(db_path))
    monkeypatch.setenv("ACTIVE_JD_PATH", str(context_dir / "active_jd.md"))
    monkeypatch.setenv("ACTIVE_RESUME_PATH", str(context_dir / "active_resume.md"))
    monkeypatch.setenv("ACTIVE_QA_PATH", str(context_dir / "active_qa.md"))
    monkeypatch.setenv("ACTIVE_CONTEXT_PATH", str(context_dir / "active_context.json"))
    yield get_settings()
