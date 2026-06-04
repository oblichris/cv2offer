from __future__ import annotations

from server.services.context_service import promote_active_context
from server.workers.interview_copilot.service import answer_from_active_context, read_copilot_events, stream_copilot_events, write_copilot_event


def test_copilot_event_write_and_read(tmp_path):
    output = tmp_path / "copilot.ndjson"

    write_copilot_event(output, "question", "请介绍项目", "可以从 AI workflow 讲起。")
    events = read_copilot_events(output)

    assert len(events) == 1
    assert events[0]["type"] == "question"
    assert events[0]["hint"] == "可以从 AI workflow 讲起。"


def test_copilot_event_stream_yields_sse_lines(tmp_path):
    output = tmp_path / "copilot.ndjson"
    write_copilot_event(output, "question", "请介绍项目", "可以从 AI workflow 讲起。")

    lines = list(stream_copilot_events(output, poll_seconds=0, max_events=1))

    assert len(lines) == 1
    assert lines[0].startswith("data: ")
    assert "可以从 AI workflow 讲起。" in lines[0]


def test_answer_from_active_context_has_non_empty_fallback(isolated_env, tmp_path, monkeypatch):
    jd = tmp_path / "jd.md"
    resume = tmp_path / "resume.md"
    qa = tmp_path / "qa.md"
    jd.write_text("AI solution consultant JD", encoding="utf-8")
    resume.write_text("AI workflow consulting resume", encoding="utf-8")
    qa.write_text("QA notes", encoding="utf-8")
    promote_active_context(jd, resume, qa, settings=isolated_env)
    monkeypatch.setattr("server.workers.interview_copilot.service.generate_answer_hint", lambda *_args, **_kwargs: "")

    hint = answer_from_active_context("请介绍一下，你如何把？")

    assert hint
    assert "MVP" in hint
