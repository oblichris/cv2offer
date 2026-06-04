from __future__ import annotations

from pathlib import Path

from server.config import PROJECT_ROOT, Settings, get_settings
from server.services import sqlite_service
from server.services.storage_service import timestamp, write_markdown
from server.workers.jd_resume.models import JDResumeRequest, JDResumeResult


def simple_fit_score(jd_text: str, resume_text: str) -> int:
    keywords = ["AI", "LLM", "product", "manager", "workflow", "MVP", "user", "metric", "roadmap", "automation"]
    combined = f"{jd_text}\n{resume_text}".lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in combined)
    return min(95, 55 + hits * 5)


def build_resume_report(request: JDResumeRequest, fit_score: int) -> str:
    return f"""# Resume Tailoring Report

## Target Role

{request.title}

## Fit Score

{fit_score}/100

## Recommended Positioning

AI product manager who can turn ambiguous user and business needs into LLM-powered workflow products, MVPs, and measurable product outcomes.

## JD Summary

{request.jd_text.strip()[:1200]}

## Resume Tailoring Suggestions

1. Put AI workflow and enterprise solution framing near the top.
2. Move product discovery, PRD, roadmap, and MVP validation examples before generic business bullets.
3. Add one bullet about user metrics, experiment design, and cross-functional delivery.

## Tailored Resume Bullets

- Converted ambiguous user needs into AI workflow product requirements, MVP scope, and measurable success metrics.
- Prioritized LLM product opportunities by user pain, business value, data readiness, and delivery complexity.
- Built a local AI job-search product with HTML frontend, Python backend, SQLite tracking, TTS/ASR services, and live copilot hints.

## Application Tracker Status

draft
"""


def generate_resume_tailoring(request: JDResumeRequest, settings: Settings | None = None) -> JDResumeResult:
    settings = settings or get_settings()
    sqlite_service.init_db(settings.db_path)
    run_id = request.run_id or sqlite_service.new_run_id("jd_resume")

    sqlite_service.record_event(run_id, "jd_parse", "Parsed JD text", db_path=settings.db_path)
    fit_score = simple_fit_score(request.jd_text, request.resume_text)
    sqlite_service.record_event(run_id, "fit_score", f"Calculated fit score {fit_score}", {"fit_score": fit_score}, db_path=settings.db_path)

    stamp = timestamp()
    jd_output_path = write_markdown(
        settings.output_dir / "jds",
        f"{stamp}_sample_jd.md",
        f"# JD Snapshot\n\n## Target Role\n\n{request.title}\n\n## JD Text\n\n{request.jd_text.strip()}\n",
    )
    output_dir = settings.output_dir / "resumes"
    filename = f"{stamp}_sample_resume_tailoring.md"
    content = build_resume_report(request, fit_score)
    output_path = write_markdown(output_dir, filename, content)

    job_id = sqlite_service.create_job(
        title=request.title,
        company=request.company,
        jd_text=request.jd_text,
        fit_score=fit_score,
        status="draft",
        db_path=settings.db_path,
    )
    resume_version_id = sqlite_service.create_resume_version(
        job_id=job_id,
        output_path=str(output_path),
        summary="MVP resume tailoring report",
        db_path=settings.db_path,
    )
    sqlite_service.record_event(
        run_id,
        "resume_write",
        f"Wrote resume tailoring output to {output_path}",
        {"output_path": str(output_path), "job_id": job_id, "resume_version_id": resume_version_id},
        db_path=settings.db_path,
    )

    return JDResumeResult(
        run_id=run_id,
        job_id=job_id,
        resume_version_id=resume_version_id,
        jd_output_path=str(jd_output_path),
        output_path=str(output_path),
        fit_score=fit_score,
        fit_summary="Strong MVP fit for AI product manager positioning.",
        next_action="Set as active context before interview preparation.",
    )
