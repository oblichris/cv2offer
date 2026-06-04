from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared in requirements.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: Path
    context_dir: Path
    output_dir: Path
    active_jd_path: Path
    active_resume_path: Path
    active_qa_path: Path
    active_context_path: Path
    mock: bool
    log_level: str


def get_settings() -> Settings:
    load_environment()
    context_dir = project_path(os.getenv("CONTEXT_DIR", "context"))
    output_dir = project_path(os.getenv("OUTPUT_DIR", "outputs"))
    return Settings(
        host=os.getenv("CV2OFFER_HOST", "127.0.0.1"),
        port=int(os.getenv("CV2OFFER_PORT", "8765")),
        db_path=project_path(os.getenv("CV2OFFER_DB_PATH", "server/db/cv2offer.sqlite")),
        context_dir=context_dir,
        output_dir=output_dir,
        active_jd_path=project_path(os.getenv("ACTIVE_JD_PATH", str(context_dir / "active_jd.md"))),
        active_resume_path=project_path(os.getenv("ACTIVE_RESUME_PATH", str(context_dir / "active_resume.md"))),
        active_qa_path=project_path(os.getenv("ACTIVE_QA_PATH", str(context_dir / "active_qa.md"))),
        active_context_path=project_path(os.getenv("ACTIVE_CONTEXT_PATH", str(context_dir / "active_context.json"))),
        mock=env_bool("CV2OFFER_MOCK", True),
        log_level=os.getenv("CV2OFFER_LOG_LEVEL", "info"),
    )
