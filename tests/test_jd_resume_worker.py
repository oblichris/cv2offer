from __future__ import annotations

from pathlib import Path

import pytest

import server.workers.jd_resume.service as jd_resume_service
from server.services import sqlite_service
from server.workers.jd_resume.models import JDResumeRequest
from server.workers.jd_resume.service import fit_summary_text, generate_resume_tailoring, simple_fit_score


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


def test_jd_resume_worker_preserves_outputs_for_same_second_runs(isolated_env, monkeypatch):
    monkeypatch.setattr(jd_resume_service, "timestamp", lambda: "20260617_061000")

    first = generate_resume_tailoring(
        JDResumeRequest(jd_text="First JD marker", resume_text="First resume marker", title="Role A"),
        settings=isolated_env,
    )
    second = generate_resume_tailoring(
        JDResumeRequest(jd_text="Second JD marker", resume_text="Second resume marker", title="Role B"),
        settings=isolated_env,
    )

    assert first.run_id != second.run_id
    assert Path(first.jd_output_path).exists()
    assert Path(first.output_path).exists()
    assert Path(second.jd_output_path).exists()
    assert Path(second.output_path).exists()
    assert first.output_path != second.output_path
    assert "First JD marker" in Path(first.jd_output_path).read_text(encoding="utf-8")
    assert "Second JD marker" in Path(second.jd_output_path).read_text(encoding="utf-8")


def test_fit_summary_text_returns_distinct_tiers():
    assert fit_summary_text(95).startswith("Strong match")
    assert fit_summary_text(85).startswith("Strong match")
    assert fit_summary_text(75).startswith("Solid match")
    assert fit_summary_text(70).startswith("Solid match")
    assert fit_summary_text(65).startswith("Moderate match")
    assert fit_summary_text(60).startswith("Moderate match")
    assert fit_summary_text(55).startswith("Limited keyword overlap")


def test_fit_summary_text_covers_full_score_range():
    for score in range(0, 101):
        summary = fit_summary_text(score)
        assert summary
        assert summary.endswith(".")


def test_generate_resume_tailoring_fit_summary_reflects_score(isolated_env):
    high = generate_resume_tailoring(
        JDResumeRequest(
            jd_text="AI LLM product manager workflow MVP user metric roadmap automation",
            resume_text="AI product manager with LLM workflow and metrics",
        ),
        settings=isolated_env,
    )
    assert high.fit_score >= 85
    assert high.fit_summary.startswith("Strong match")

    low = generate_resume_tailoring(
        JDResumeRequest(jd_text="generic office role", resume_text="generic background"),
        settings=isolated_env,
    )
    assert low.fit_score == 55
    assert low.fit_summary.startswith("Limited keyword overlap")
