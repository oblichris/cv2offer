from __future__ import annotations

from fastapi.testclient import TestClient

from server.app import app


def test_active_context_endpoint_reports_missing_context(isolated_env):
    with TestClient(app) as client:
        response = client.get("/api/context/active")

    assert response.status_code == 200
    assert response.json()["exists"] is False


def test_active_context_endpoint_returns_editable_content(isolated_env, tmp_path):
    jd = tmp_path / "jd.md"
    resume = tmp_path / "resume.md"
    qa = tmp_path / "qa.md"
    jd.write_text("JD editable marker", encoding="utf-8")
    resume.write_text("Resume editable marker", encoding="utf-8")
    qa.write_text("QA editable marker", encoding="utf-8")

    with TestClient(app) as client:
        promote = client.post(
            "/api/context/promote",
            json={"source_jd_path": str(jd), "source_resume_path": str(resume), "source_qa_path": str(qa)},
        )
        assert promote.status_code == 200
        response = client.get("/api/context/active")

    assert response.status_code == 200
    payload = response.json()
    assert payload["jd"] == "JD editable marker"
    assert payload["resume"] == "Resume editable marker"
    assert payload["qa"] == "QA editable marker"


def test_active_context_endpoint_updates_editable_content(isolated_env):
    with TestClient(app) as client:
        response = client.put(
            "/api/context/active",
            json={"jd": "Edited JD", "resume": "Edited resume", "qa": "Edited QA"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jd"] == "Edited JD"
    assert payload["resume"] == "Edited resume"
    assert payload["qa"] == "Edited QA"
    assert "edited_at" in payload["metadata"]


def test_jd_resume_api_returns_jd_snapshot(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/jd-resume",
            json={"jd_text": "Custom JD marker", "resume_text": "Resume marker", "title": "Custom Role"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jd_output_path"]
    assert payload["output_path"]


def test_tracking_summary_endpoint(isolated_env):
    with TestClient(app) as client:
        client.post(
            "/api/jd-resume",
            json={"jd_text": "AI PM JD", "resume_text": "AI PM resume", "title": "AI Product Manager"},
        )
        response = client.get("/api/tracking/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["jobs"] == 1
    assert payload["recent_jobs"][0]["title"] == "AI Product Manager"


def test_interview_session_api_flow(isolated_env, tmp_path):
    jd = tmp_path / "jd.md"
    resume = tmp_path / "resume.md"
    qa = tmp_path / "qa.md"
    jd.write_text("JD marker", encoding="utf-8")
    resume.write_text("Resume marker", encoding="utf-8")
    qa.write_text("QA marker", encoding="utf-8")

    with TestClient(app) as client:
        promote = client.post(
            "/api/context/promote",
            json={"source_jd_path": str(jd), "source_resume_path": str(resume), "source_qa_path": str(qa)},
        )
        assert promote.status_code == 200
        started = client.post("/api/interview-prep/session/start", json={})
        assert started.status_code == 200
        start_payload = started.json()
        answer = client.post(
            "/api/interview-prep/session/answer",
            json={
                "run_id": start_payload["run_id"],
                "question_index": 1,
                "answer_text": "我的回答会结合 JD 和项目。",
            },
        )

    assert answer.status_code == 200
    assert answer.json()["next_question"]
