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


def test_audio_file_endpoint_serves_output_audio(isolated_env):
    audio_path = isolated_env.output_dir / "sessions" / "sample.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF....WAVE")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(audio_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == b"RIFF....WAVE"


def test_audio_file_endpoint_rejects_paths_outside_output_dir(isolated_env, tmp_path):
    private_file = tmp_path / "private.txt"
    private_file.write_text("private marker", encoding="utf-8")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(private_file)})

    assert response.status_code == 400
    assert "output directory" in response.json()["detail"]


def test_audio_file_endpoint_returns_correct_content_type_for_ogg(isolated_env):
    audio_path = isolated_env.output_dir / "sessions" / "sample.ogg"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake-audio")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(audio_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/ogg")


def test_audio_file_endpoint_returns_correct_content_type_for_webm(isolated_env):
    audio_path = isolated_env.output_dir / "sessions" / "sample.webm"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake-audio")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(audio_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/webm")


def test_audio_file_endpoint_returns_correct_content_type_for_m4a(isolated_env):
    audio_path = isolated_env.output_dir / "sessions" / "sample.m4a"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake-audio")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(audio_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mp4")


def test_audio_file_endpoint_unknown_extension_returns_octet_stream(isolated_env):
    audio_path = isolated_env.output_dir / "sessions" / "sample.dat"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake-audio")

    with TestClient(app) as client:
        response = client.get("/api/files/audio", params={"path": str(audio_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")


def test_health_endpoint(isolated_env):
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mock"] == "True"


def test_jd_resume_rejects_empty_jd_text(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/jd-resume",
            json={"jd_text": "", "resume_text": "valid resume", "title": "Role"},
        )

    assert response.status_code == 422


def test_jd_resume_rejects_empty_resume_text(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/jd-resume",
            json={"jd_text": "valid JD", "resume_text": "", "title": "Role"},
        )

    assert response.status_code == 422


def test_interview_answer_rejects_empty_run_id(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/interview-prep/session/answer",
            json={"run_id": "", "question_index": 1, "answer_text": "answer"},
        )

    assert response.status_code == 422


def test_interview_answer_rejects_zero_question_index(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/interview-prep/session/answer",
            json={"run_id": "some-run", "question_index": 0, "answer_text": "answer"},
        )

    assert response.status_code == 422


def test_interview_answer_rejects_negative_question_index(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/interview-prep/session/answer",
            json={"run_id": "some-run", "question_index": -1, "answer_text": "answer"},
        )

    assert response.status_code == 422


def test_events_endpoint_returns_stored_events(isolated_env):
    with TestClient(app) as client:
        resp = client.post(
            "/api/jd-resume",
            json={"jd_text": "AI PM JD", "resume_text": "AI PM resume", "title": "AI PM"},
        )
        run_id = resp.json()["run_id"]
        events_resp = client.get(f"/api/events/{run_id}")

    assert events_resp.status_code == 200
    events = events_resp.json()["events"]
    assert len(events) >= 1
    assert events[0]["run_id"] == run_id


def test_promote_rejects_empty_source_jd_path(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/context/promote",
            json={"source_jd_path": "", "source_resume_path": "/some/resume.md"},
        )

    assert response.status_code == 422


def test_promote_rejects_empty_source_resume_path(isolated_env):
    with TestClient(app) as client:
        response = client.post(
            "/api/context/promote",
            json={"source_jd_path": "/some/jd.md", "source_resume_path": ""},
        )

    assert response.status_code == 422


def test_active_context_update_rejects_empty_jd(isolated_env):
    with TestClient(app) as client:
        response = client.put(
            "/api/context/active",
            json={"jd": "", "resume": "valid resume", "qa": "valid qa"},
        )

    assert response.status_code == 422


def test_active_context_update_rejects_empty_resume(isolated_env):
    with TestClient(app) as client:
        response = client.put(
            "/api/context/active",
            json={"jd": "valid jd", "resume": "", "qa": "valid qa"},
        )

    assert response.status_code == 422


def test_active_context_update_rejects_empty_qa(isolated_env):
    with TestClient(app) as client:
        response = client.put(
            "/api/context/active",
            json={"jd": "valid jd", "resume": "valid resume", "qa": ""},
        )

    assert response.status_code == 422


def test_interview_session_start_rejects_zero_question_count(isolated_env, tmp_path):
    jd = tmp_path / "jd.md"
    resume = tmp_path / "resume.md"
    qa = tmp_path / "qa.md"
    jd.write_text("JD", encoding="utf-8")
    resume.write_text("Resume", encoding="utf-8")
    qa.write_text("QA", encoding="utf-8")

    with TestClient(app) as client:
        client.post(
            "/api/context/promote",
            json={"source_jd_path": str(jd), "source_resume_path": str(resume), "source_qa_path": str(qa)},
        )
        response = client.post("/api/interview-prep/session/start", json={"question_count": 0})

    assert response.status_code == 422


def test_interview_session_start_rejects_negative_question_count(isolated_env, tmp_path):
    jd = tmp_path / "jd.md"
    resume = tmp_path / "resume.md"
    qa = tmp_path / "qa.md"
    jd.write_text("JD", encoding="utf-8")
    resume.write_text("Resume", encoding="utf-8")
    qa.write_text("QA", encoding="utf-8")

    with TestClient(app) as client:
        client.post(
            "/api/context/promote",
            json={"source_jd_path": str(jd), "source_resume_path": str(resume), "source_qa_path": str(qa)},
        )
        response = client.post("/api/interview-prep/session/start", json={"question_count": -1})

    assert response.status_code == 422
