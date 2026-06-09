from __future__ import annotations

from pydantic import BaseModel, Field


class JDResumeRequest(BaseModel):
    jd_text: str = Field(..., min_length=1)
    resume_text: str = Field(..., min_length=1)
    title: str = "Sample AI Product Manager"
    company: str | None = None
    run_id: str | None = None


class JDResumeResult(BaseModel):
    run_id: str
    job_id: int
    resume_version_id: int
    jd_output_path: str
    output_path: str
    fit_score: int
    fit_summary: str
    next_action: str
