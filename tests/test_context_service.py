from __future__ import annotations

import json
from pathlib import Path

from server.services.context_service import promote_active_context, read_active_context


def test_context_promotion_writes_active_files(isolated_env, tmp_path: Path):
    jd = tmp_path / "sample-jd.md"
    resume = tmp_path / "sample-resume.md"
    qa = tmp_path / "sample-qa.md"
    jd.write_text("JD text", encoding="utf-8")
    resume.write_text("Resume text", encoding="utf-8")
    qa.write_text("QA text", encoding="utf-8")

    metadata = promote_active_context(jd, resume, qa, job_id=1, resume_version_id=2, qa_pack_id=3, settings=isolated_env)

    assert isolated_env.active_jd_path.read_text(encoding="utf-8") == "JD text"
    assert isolated_env.active_resume_path.read_text(encoding="utf-8") == "Resume text"
    assert isolated_env.active_qa_path.read_text(encoding="utf-8") == "QA text"
    stored = json.loads(isolated_env.active_context_path.read_text(encoding="utf-8"))
    assert stored["job_id"] == 1
    assert stored["resume_version_id"] == 2
    assert stored["qa_pack_id"] == 3
    assert "promoted_at" in stored
    assert metadata == stored


def test_context_promotion_does_not_mutate_generated_output(isolated_env, tmp_path: Path):
    jd = tmp_path / "sample-jd.md"
    generated_resume = tmp_path / "outputs" / "resumes" / "sample_resume_tailoring.md"
    jd.write_text("JD text", encoding="utf-8")
    generated_resume.parent.mkdir(parents=True)
    generated_resume.write_text("Original generated resume", encoding="utf-8")

    promote_active_context(jd, generated_resume, settings=isolated_env)
    isolated_env.active_resume_path.write_text("Edited active resume", encoding="utf-8")

    assert generated_resume.read_text(encoding="utf-8") == "Original generated resume"
    assert isolated_env.active_resume_path.read_text(encoding="utf-8") == "Edited active resume"


def test_read_active_context_uses_context_files(isolated_env, tmp_path: Path):
    jd = tmp_path / "sample-jd.md"
    generated_resume = tmp_path / "outputs" / "resumes" / "sample_resume_tailoring.md"
    jd.write_text("JD text", encoding="utf-8")
    generated_resume.parent.mkdir(parents=True)
    generated_resume.write_text("Generated resume", encoding="utf-8")
    promote_active_context(jd, generated_resume, settings=isolated_env)
    generated_resume.rename(generated_resume.with_suffix(".deleted"))

    isolated_env.active_resume_path.write_text("Active resume survives", encoding="utf-8")
    context = read_active_context(isolated_env)

    assert context["resume"] == "Active resume survives"
