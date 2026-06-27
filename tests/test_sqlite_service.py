from __future__ import annotations

from server.services import sqlite_service


def test_sqlite_initializes_required_tables(isolated_env):
    sqlite_service.init_db(isolated_env.db_path)
    assert {
        "jobs",
        "resume_versions",
        "applications",
        "qa_packs",
        "interview_prep_packs",
        "sessions",
        "events",
    }.issubset(sqlite_service.table_names(isolated_env.db_path))


def test_sqlite_records_events_in_stage_order(isolated_env):
    run_id = "test-run"
    sqlite_service.record_event(run_id, "jd_parse", "Parsed JD", db_path=isolated_env.db_path)
    sqlite_service.record_event(run_id, "fit_score", "Scored fit", db_path=isolated_env.db_path)
    sqlite_service.record_event(run_id, "resume_write", "Wrote resume", db_path=isolated_env.db_path)

    events = sqlite_service.get_events(run_id, isolated_env.db_path)

    assert [event["stage"] for event in events] == ["jd_parse", "fit_score", "resume_write"]


def test_tracking_summary_counts_and_recent_rows(isolated_env):
    job_id = sqlite_service.create_job(
        title="AI Product Manager",
        jd_text="JD",
        fit_score=88,
        status="draft",
        db_path=isolated_env.db_path,
    )
    sqlite_service.create_resume_version(job_id, "outputs/resumes/sample.md", db_path=isolated_env.db_path)
    sqlite_service.create_interview_prep_pack(
        output_path="outputs/interview_50q/sample.md",
        question_count=5,
        job_id=job_id,
        db_path=isolated_env.db_path,
    )
    sqlite_service.create_session("interview_prep", "running", "outputs/sessions/sample.md", db_path=isolated_env.db_path)
    sqlite_service.record_event("run-1", "jd_parse", "Parsed JD", db_path=isolated_env.db_path)

    summary = sqlite_service.tracking_summary(isolated_env.db_path)

    assert summary["counts"]["jobs"] == 1
    assert summary["counts"]["resume_versions"] == 1
    assert summary["counts"]["interview_prep_packs"] == 1
    assert summary["counts"]["sessions"] == 1
    assert summary["counts"]["events"] == 1
    assert summary["recent_jobs"][0]["title"] == "AI Product Manager"


def test_tracking_summary_lists_recent_interview_prep_packs_ordered(isolated_env):
    job_id = sqlite_service.create_job(title="Backend Engineer", jd_text="JD", db_path=isolated_env.db_path)
    first = sqlite_service.create_interview_prep_pack(
        output_path="outputs/interview_50q/first.md", question_count=5, job_id=job_id, db_path=isolated_env.db_path
    )
    second = sqlite_service.create_interview_prep_pack(
        output_path="outputs/interview_50q/second.md", question_count=50, job_id=job_id, db_path=isolated_env.db_path
    )

    prep_packs = sqlite_service.tracking_summary(isolated_env.db_path)["recent_interview_prep_packs"]

    assert [pack["id"] for pack in prep_packs] == [second, first]
    assert prep_packs[0]["output_path"] == "outputs/interview_50q/second.md"
    assert prep_packs[0]["question_count"] == 50
    assert prep_packs[1]["output_path"] == "outputs/interview_50q/first.md"


def test_update_session_status_persists_new_status(isolated_env):
    session_id = sqlite_service.create_session("interview_prep", "running", db_path=isolated_env.db_path)

    sqlite_service.update_session_status(session_id, "completed", db_path=isolated_env.db_path)

    row = sqlite_service.get_row("sessions", session_id, isolated_env.db_path)
    assert row["status"] == "completed"
    assert row["updated_at"] >= row["created_at"]
