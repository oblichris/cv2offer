from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class JDResumeRequest(BaseModel):
    jd_text: str = Field(..., min_length=1)
    resume_text: str = Field(..., min_length=1)
    title: str = "Sample AI Product Manager"
    company: str | None = None
    run_id: str | None = None

    @field_validator("jd_text", "resume_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank or whitespace-only")
        return value


class JDResumeResult(BaseModel):
    run_id: str
    job_id: int
    resume_version_id: int
    jd_output_path: str
    output_path: str
    fit_score: int
    fit_summary: str
    next_action: str
