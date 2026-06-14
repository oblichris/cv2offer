from __future__ import annotations

import json
import re
from pathlib import Path

from server.config import Settings, get_settings
from server.services import sqlite_service
from server.services.context_service import read_active_context
from server.services.asr_service import transcribe_audio_base64
from server.services.llm_service import generate_text, review_interview_answer
from server.services.storage_service import timestamp, write_markdown
from server.services.tts_service import synthesize_speech
from server.workers.interview_prep.models import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewPrepRequest,
    InterviewPrepResult,
    InterviewSessionStartRequest,
    InterviewSessionStartResult,
)


def numbered_questions(content: str) -> int:
    return len(re.findall(r"(?m)^\d+\.\s+", content))


def build_mock_questions(jd: str, resume: str, qa: str, count: int = 5) -> str:
    prompts = [
        "请用 2 分钟介绍你自己，并突出与这个岗位最相关的经历。",
        "这个 JD 最核心的业务问题是什么？你会如何拆解？",
        "请讲一个你把咨询方法转成可执行工作流的案例。",
        "如果面试官质疑你技术深度不够，你怎么回应？",
        "请结合你的 QA 准备，说明为什么你适合这个岗位。",
    ]
    body = "\n".join(f"{idx}. {question}" for idx, question in enumerate(prompts[:count], start=1))
    return f"""# Interview Prep Pack

## Context Snapshot

JD length: {len(jd)}

Resume length: {len(resume)}

QA length: {len(qa)}

## Questions

{body}
"""


def get_mock_question_list(count: int = 5) -> list[str]:
    prompts = [
        "请用 2 分钟介绍你自己，并突出与这个岗位最相关的经历。",
        "这个 JD 最核心的业务问题是什么？你会如何拆解？",
        "请讲一个你把咨询方法转成可执行工作流的案例。",
        "如果面试官质疑你技术深度不够，你怎么回应？",
        "请结合你的 QA 准备，说明为什么你适合这个岗位。",
    ]
    return prompts[:count]


def parse_numbered_questions(text: str) -> list[str]:
    questions: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*\d+[\.\)、]\s*(.+?)\s*$", line)
        if match:
            questions.append(match.group(1))
    return questions


def build_question_list(context: dict[str, str], count: int, settings: Settings) -> list[str]:
    if settings.mock:
        return get_mock_question_list(count)
    prompt = (
        f"请基于以下JD、简历和QA生成 {count} 道面试前辅导问题。"
        "要求只输出编号列表，每行一道题，不要解释。\n\n"
        f"JD:\n{context.get('jd', '')[:2500]}\n\n"
        f"简历:\n{context.get('resume', '')[:2500]}\n\n"
        f"QA:\n{context.get('qa', '')[:1500]}"
    )
    parsed = parse_numbered_questions(generate_text(prompt))
    fallback = get_mock_question_list(5)
    while len(parsed) < count:
        parsed.append(fallback[len(parsed) % len(fallback)])
    return parsed[:count]


def session_state_path(settings: Settings, run_id: str) -> Path:
    return settings.output_dir / "sessions" / f"{run_id}.json"


def session_markdown_path(settings: Settings, run_id: str) -> Path:
    return settings.output_dir / "sessions" / f"{run_id}.md"


def question_audio_path(settings: Settings, run_id: str, index: int) -> Path:
    suffix = "wav" if settings.mock else "mp3"
    return settings.output_dir / "sessions" / f"{run_id}_q{index}.{suffix}"


def save_state(settings: Settings, run_id: str, state: dict) -> None:
    path = session_state_path(settings, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(settings: Settings, run_id: str) -> dict:
    path = session_state_path(settings, run_id)
    if not path.exists():
        raise FileNotFoundError(f"Missing interview session state: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_question_audio(settings: Settings, run_id: str, index: int, question: str) -> Path:
    audio = synthesize_speech(question)
    path = question_audio_path(settings, run_id, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return path


def render_session_markdown(state: dict) -> str:
    lines = [
        "# Interview Coaching Session",
        "",
        f"Run ID: `{state['run_id']}`",
        "",
    ]
    for item in state.get("records", []):
        lines.extend(
            [
                f"## Question {item['question_index']}",
                "",
                f"**Question:** {item['question']}",
                "",
                f"**Transcript:** {item['transcript']}",
                "",
                f"**Feedback:** {item['feedback']}",
                "",
            ]
        )
    return "\n".join(lines)


def generate_interview_prep(request: InterviewPrepRequest | None = None, settings: Settings | None = None) -> InterviewPrepResult:
    request = request or InterviewPrepRequest()
    settings = settings or get_settings()
    sqlite_service.init_db(settings.db_path)
    run_id = request.run_id or sqlite_service.new_run_id("interview_prep")
    context = read_active_context(settings)
    sqlite_service.record_event(run_id, "context_read", "Read active interview context", context["paths"], db_path=settings.db_path)

    question_count = 5 if settings.mock else 50
    questions = build_question_list({"jd": context["jd"], "resume": context["resume"], "qa": context["qa"]}, question_count, settings)
    body = "\n".join(f"{idx}. {question}" for idx, question in enumerate(questions, start=1))
    content = f"""# Interview Prep Pack

## Context Snapshot

JD length: {len(context["jd"])}

Resume length: {len(context["resume"])}

QA length: {len(context["qa"])}

## Questions

{body}
"""

    output_path = write_markdown(settings.output_dir / "interview_50q", f"{timestamp()}_sample_interview_50q.md", content)
    actual_count = numbered_questions(content)
    prep_id = sqlite_service.create_interview_prep_pack(
        output_path=str(output_path),
        question_count=actual_count,
        job_id=context["metadata"].get("job_id"),
        resume_version_id=context["metadata"].get("resume_version_id"),
        qa_pack_id=context["metadata"].get("qa_pack_id"),
        db_path=settings.db_path,
    )
    sqlite_service.record_event(
        run_id,
        "interview_pack_write",
        f"Wrote interview prep pack to {output_path}",
        {"output_path": str(output_path), "question_count": actual_count},
        db_path=settings.db_path,
    )
    return InterviewPrepResult(
        run_id=run_id,
        output_path=str(output_path),
        question_count=actual_count,
        interview_prep_pack_id=prep_id,
    )


def start_interview_session(request: InterviewSessionStartRequest | None = None, settings: Settings | None = None) -> InterviewSessionStartResult:
    request = request or InterviewSessionStartRequest()
    settings = settings or get_settings()
    sqlite_service.init_db(settings.db_path)
    context = read_active_context(settings)
    run_id = sqlite_service.new_run_id("interview_session")
    question_count = request.question_count or (5 if settings.mock else 50)
    questions = build_question_list(context, question_count, settings)
    session_path = session_markdown_path(settings, run_id)
    session_id = sqlite_service.create_session(kind="interview_prep", status="running", output_path=str(session_path), db_path=settings.db_path)
    first_audio = write_question_audio(settings, run_id, 1, questions[0])
    state = {
        "run_id": run_id,
        "session_id": session_id,
        "questions": questions,
        "records": [],
        "context": {"jd": context["jd"], "resume": context["resume"], "qa": context["qa"]},
        "metadata": context["metadata"],
        "session_path": str(session_path),
    }
    save_state(settings, run_id, state)
    session_path.write_text(render_session_markdown(state), encoding="utf-8")
    sqlite_service.record_event(run_id, "session_start", "Started interview coaching session", {"session_id": session_id}, db_path=settings.db_path)
    sqlite_service.record_event(run_id, "tts_question", "Generated TTS for question 1", {"audio_path": str(first_audio)}, db_path=settings.db_path)
    return InterviewSessionStartResult(
        run_id=run_id,
        session_id=session_id,
        session_path=str(session_path),
        question=questions[0],
        question_index=1,
        question_count=len(questions),
        audio_path=str(first_audio),
    )


def submit_interview_answer(request: InterviewAnswerRequest, settings: Settings | None = None) -> InterviewAnswerResult:
    settings = settings or get_settings()
    state = load_state(settings, request.run_id)
    questions = state["questions"]
    if request.question_index < 1 or request.question_index > len(questions):
        raise ValueError(f"question_index out of range: {request.question_index}")
    question = questions[request.question_index - 1]
    transcript = request.answer_text or ""
    if not transcript and request.audio_base64:
        transcript = transcribe_audio_base64(request.audio_base64, request.audio_mime_type)
    if not transcript:
        raise ValueError("Either answer_text or audio_base64 is required.")
    sqlite_service.record_event(request.run_id, "asr_transcript", "Captured answer transcript", {"question_index": request.question_index}, db_path=settings.db_path)
    feedback = review_interview_answer(question, transcript, state.get("context", {}))
    sqlite_service.record_event(request.run_id, "llm_feedback", "Generated interview feedback", {"question_index": request.question_index}, db_path=settings.db_path)
    record = {
        "question_index": request.question_index,
        "question": question,
        "transcript": transcript,
        "feedback": feedback,
    }
    state.setdefault("records", []).append(record)
    next_question = None
    next_audio_path = None
    if request.question_index < len(questions):
        next_question = questions[request.question_index]
        next_audio_path = str(write_question_audio(settings, request.run_id, request.question_index + 1, next_question))
        sqlite_service.record_event(request.run_id, "tts_question", f"Generated TTS for question {request.question_index + 1}", {"audio_path": next_audio_path}, db_path=settings.db_path)
    save_state(settings, request.run_id, state)
    path = Path(state["session_path"])
    path.write_text(render_session_markdown(state), encoding="utf-8")
    return InterviewAnswerResult(
        run_id=request.run_id,
        session_id=state["session_id"],
        question_index=request.question_index,
        question=question,
        transcript=transcript,
        feedback=feedback,
        session_path=str(path),
        next_question=next_question,
        next_audio_path=next_audio_path,
    )
