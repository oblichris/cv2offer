from __future__ import annotations

from pathlib import Path

from server.services import sqlite_service
from server.workers.jd_resume.models import JDResumeRequest
from server.workers.jd_resume.service import generate_resume_tailoring


def test_jd_resume_worker_writes_output_and_records(isolated_env):
    result = generate_resume_tailoring(
        JDResumeRequest(jd_text="AI solution consultant JD", resume_text="AI workflow resume"),
        settings=isolated_env,
    )

    assert Path(result.output_path).exists()
    assert Path(result.jd_output_path).exists()
    assert "AI solution consultant JD" in Path(result.jd_output_path).read_text(encoding="utf-8")
    assert sqlite_service.get_row("jobs", result.job_id, isolated_env.db_path) is not None
    assert sqlite_service.get_row("resume_versions", result.resume_version_id, isolated_env.db_path) is not None
    events = sqlite_service.get_events(result.run_id, isolated_env.db_path)
    assert [event["stage"] for event in events] == ["jd_parse", "fit_score", "resume_write"]
