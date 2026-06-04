from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from server.config import PROJECT_ROOT, Settings, get_settings


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_or_initialize(source_path: Path | None, destination_path: Path, default_text: str = "") -> None:
    ensure_parent(destination_path)
    if source_path and source_path.exists():
        shutil.copyfile(source_path, destination_path)
    else:
        destination_path.write_text(default_text, encoding="utf-8")


def promote_active_context(
    source_jd_path: str | Path,
    source_resume_path: str | Path,
    source_qa_path: str | Path | None = None,
    job_id: int | None = None,
    resume_version_id: int | None = None,
    qa_pack_id: int | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    source_jd = Path(source_jd_path)
    source_resume = Path(source_resume_path)
    source_qa = Path(source_qa_path) if source_qa_path else None
    if not source_jd.is_absolute():
        source_jd = PROJECT_ROOT / source_jd
    if not source_resume.is_absolute():
        source_resume = PROJECT_ROOT / source_resume
    if source_qa and not source_qa.is_absolute():
        source_qa = PROJECT_ROOT / source_qa

    if not source_jd.exists():
        raise FileNotFoundError(f"Missing source JD file: {source_jd}")
    if not source_resume.exists():
        raise FileNotFoundError(f"Missing source resume file: {source_resume}")

    copy_or_initialize(source_jd, settings.active_jd_path)
    copy_or_initialize(source_resume, settings.active_resume_path)
    copy_or_initialize(source_qa, settings.active_qa_path, "# Active QA\n\nNo QA pack selected yet.\n")

    metadata = {
        "job_id": job_id,
        "resume_version_id": resume_version_id,
        "qa_pack_id": qa_pack_id,
        "source_jd_path": rel(source_jd),
        "source_resume_path": rel(source_resume),
        "source_qa_path": rel(source_qa) if source_qa else None,
        "active_jd_path": rel(settings.active_jd_path),
        "active_resume_path": rel(settings.active_resume_path),
        "active_qa_path": rel(settings.active_qa_path),
        "promoted_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    }
    ensure_parent(settings.active_context_path)
    settings.active_context_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def read_active_context(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    missing = [
        str(path)
        for path in (settings.active_jd_path, settings.active_resume_path, settings.active_qa_path)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing active context file(s): {', '.join(missing)}")
    metadata: dict[str, Any] = {}
    if settings.active_context_path.exists():
        metadata = json.loads(settings.active_context_path.read_text(encoding="utf-8"))
    return {
        "jd": settings.active_jd_path.read_text(encoding="utf-8"),
        "resume": settings.active_resume_path.read_text(encoding="utf-8"),
        "qa": settings.active_qa_path.read_text(encoding="utf-8"),
        "metadata": metadata,
        "paths": {
            "active_jd_path": str(settings.active_jd_path),
            "active_resume_path": str(settings.active_resume_path),
            "active_qa_path": str(settings.active_qa_path),
            "active_context_path": str(settings.active_context_path),
        },
    }


def update_active_context(
    jd: str,
    resume: str,
    qa: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    ensure_parent(settings.active_jd_path)
    ensure_parent(settings.active_resume_path)
    ensure_parent(settings.active_qa_path)
    settings.active_jd_path.write_text(jd, encoding="utf-8")
    settings.active_resume_path.write_text(resume, encoding="utf-8")
    settings.active_qa_path.write_text(qa, encoding="utf-8")

    metadata: dict[str, Any] = {}
    if settings.active_context_path.exists():
        metadata = json.loads(settings.active_context_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "active_jd_path": rel(settings.active_jd_path),
            "active_resume_path": rel(settings.active_resume_path),
            "active_qa_path": rel(settings.active_qa_path),
            "edited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        }
    )
    ensure_parent(settings.active_context_path)
    settings.active_context_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return read_active_context(settings)
