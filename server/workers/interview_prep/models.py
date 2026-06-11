from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewPrepRequest(BaseModel):
    run_id: str | None = None


class InterviewPrepResult(BaseModel):
    run_id: str
    output_path: str
    question_count: int
    interview_prep_pack_id: int


class InterviewSessionStartRequest(BaseModel):
    question_count: int | None = Field(None, ge=1)


class InterviewSessionStartResult(BaseModel):
    run_id: str
    session_id: int
    session_path: str
    question: str
    question_index: int
    question_count: int
    audio_path: str


class InterviewAnswerRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    question_index: int = Field(..., ge=1)
    answer_text: str | None = None
    audio_base64: str | None = None
    audio_mime_type: str = "audio/wav"


class InterviewAnswerResult(BaseModel):
    run_id: str
    session_id: int
    question_index: int
    question: str
    transcript: str
    feedback: str
    session_path: str
    next_question: str | None = None
    next_audio_path: str | None = None
