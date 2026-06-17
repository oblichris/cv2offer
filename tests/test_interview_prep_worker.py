from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import pytest

from server.services import sqlite_service
from server.services.context_service import promote_active_context
from server.workers.interview_prep.models import InterviewAnswerRequest, InterviewSessionStartRequest
from server.workers.interview_prep.service import generate_interview_prep, get_mock_question_list, numbered_questions, start_interview_session, submit_interview_answer


def prepare_context(settings, tmp_path: Path) -> Path:
    jd = tmp_path / "sample-jd.md"
    resume = tmp_path / "outputs" / "resumes" / "sample_resume_tailoring.md"
    qa = tmp_path / "sample-qa.md"
    jd.write_text("JD: AI solution consultant", encoding="utf-8")
    resume.parent.mkdir(parents=True)
    resume.write_text("Resume: active AI workflow story", encoding="utf-8")
    qa.write_text("QA: why this role", encoding="utf-8")
    promote_active_context(jd, resume, qa, settings=settings)
    return resume


def test_interview_prep_reads_active_context_and_writes_five_questions(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)

    result = generate_interview_prep(settings=isolated_env)
    output = Path(result.output_path).read_text(encoding="utf-8")

    assert result.question_count == 5
    assert numbered_questions(output) == 5
    assert sqlite_service.get_row("interview_prep_packs", result.interview_prep_pack_id, isolated_env.db_path) is not None


def test_interview_prep_real_mode_generates_50_questions(isolated_env, tmp_path: Path, monkeypatch):
    prepare_context(isolated_env, tmp_path)
    real_settings = replace(isolated_env, mock=False)
    monkeypatch.setattr(
        "server.workers.interview_prep.service.generate_text",
        lambda prompt: "\n".join(f"{idx}. 真实模式问题 {idx}" for idx in range(1, 51)),
    )

    result = generate_interview_prep(settings=real_settings)
    output = Path(result.output_path).read_text(encoding="utf-8")

    assert result.question_count == 50
    assert numbered_questions(output) == 50


def test_interview_prep_fails_without_context(isolated_env):
    with pytest.raises(FileNotFoundError) as exc:
        generate_interview_prep(settings=isolated_env)
    assert "Missing active context file" in str(exc.value)


def test_interview_prep_does_not_read_generated_outputs_after_promotion(isolated_env, tmp_path: Path):
    generated_resume = prepare_context(isolated_env, tmp_path)
    generated_resume.rename(generated_resume.with_suffix(".deleted"))
    edited_resume = "Edited active resume with unique marker"
    isolated_env.active_resume_path.write_text(edited_resume, encoding="utf-8")

    result = generate_interview_prep(settings=isolated_env)
    output = Path(result.output_path).read_text(encoding="utf-8")

    assert result.question_count == 5
    assert f"Resume length: {len(edited_resume)}" in output
    assert Path(result.output_path).exists()


def test_interactive_interview_session_tts_answer_feedback_and_save(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)

    started = start_interview_session(settings=isolated_env)
    assert started.question_index == 1
    assert started.question_count == 5
    assert Path(started.audio_path).exists()
    assert Path(started.audio_path).suffix == ".wav"

    answered = submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=1,
            answer_text="我会用咨询拆解能力识别业务场景，再用 AI workflow 做 MVP。",
        ),
        settings=isolated_env,
    )

    assert "咨询拆解能力" in answered.transcript
    assert "[mock llm]" in answered.feedback
    assert answered.next_question is not None
    assert answered.next_audio_path is not None
    session_text = Path(answered.session_path).read_text(encoding="utf-8")
    assert "Interview Coaching Session" in session_text
    assert "咨询拆解能力" in session_text


def test_interactive_interview_session_accepts_audio_base64_for_asr(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)
    started = start_interview_session(settings=isolated_env)

    answered = submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=1,
            audio_base64="UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=",
            audio_mime_type="audio/wav",
        ),
        settings=isolated_env,
    )

    assert "mock ASR 转写" in answered.transcript
    assert "[mock llm]" in answered.feedback


def test_interactive_session_respects_fewer_questions_in_mock(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)

    started = start_interview_session(
        InterviewSessionStartRequest(question_count=3),
        settings=isolated_env,
    )

    assert started.question_count == 3
    assert started.question_index == 1


def test_interactive_session_respects_custom_question_count_in_mock(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)

    started = start_interview_session(
        InterviewSessionStartRequest(question_count=2),
        settings=isolated_env,
    )
    answered = submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=1,
            answer_text="第一题回答。",
        ),
        settings=isolated_env,
    )

    assert answered.next_question is not None
    assert answered.next_audio_path is not None

    final = submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=2,
            answer_text="第二题回答。",
        ),
        settings=isolated_env,
    )

    assert final.next_question is None
    assert final.next_audio_path is None


def test_mock_question_list_pads_beyond_base_pool():
    questions = get_mock_question_list(8)

    assert len(questions) == 8


def test_interactive_session_respects_more_questions_than_mock_pool_in_mock(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)

    started = start_interview_session(
        InterviewSessionStartRequest(question_count=8),
        settings=isolated_env,
    )

    assert started.question_count == 8
    assert started.question_index == 1


def test_interactive_session_marks_completed_after_final_answer(isolated_env, tmp_path: Path):
    prepare_context(isolated_env, tmp_path)
    started = start_interview_session(
        InterviewSessionStartRequest(question_count=2),
        settings=isolated_env,
    )
    session_id = started.session_id

    submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=1,
            answer_text="第一题回答。",
        ),
        settings=isolated_env,
    )
    mid_row = sqlite_service.get_row("sessions", session_id, isolated_env.db_path)
    assert mid_row["status"] == "running"

    submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=2,
            answer_text="最后一题回答。",
        ),
        settings=isolated_env,
    )

    final_row = sqlite_service.get_row("sessions", session_id, isolated_env.db_path)
    assert final_row["status"] == "completed"
    stages = [event["stage"] for event in sqlite_service.get_events(started.run_id, isolated_env.db_path)]
    assert "session_complete" in stages
