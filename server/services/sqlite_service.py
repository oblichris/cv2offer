from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from server.config import PROJECT_ROOT, get_settings


SCHEMA_PATH = PROJECT_ROOT / "server" / "db" / "schema.sql"


def get_db_path(db_path: Path | None = None) -> Path:
    return db_path or get_settings().db_path


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return path


def table_names(db_path: Path | None = None) -> set[str]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def new_run_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def record_event(run_id: str, stage: str, message: str, payload: dict[str, Any] | None = None, db_path: Path | None = None) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO events (run_id, stage, message, payload_json) VALUES (?, ?, ?, ?)",
            (run_id, stage, message, json.dumps(payload or {}, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def record_events(run_id: str, events: Iterable[tuple[str, str]], db_path: Path | None = None) -> None:
    for stage, message in events:
        record_event(run_id, stage, message, db_path=db_path)


def get_events(run_id: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY id ASC", (run_id,)).fetchall()
    return [dict(row) for row in rows]


def create_job(title: str, jd_text: str, company: str | None = None, fit_score: int | None = None, status: str = "draft", db_path: Path | None = None) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (title, company, jd_text, fit_score, status) VALUES (?, ?, ?, ?, ?)",
            (title, company, jd_text, fit_score, status),
        )
        return int(cursor.lastrowid)


def create_resume_version(job_id: int | None, output_path: str, summary: str = "", db_path: Path | None = None) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO resume_versions (job_id, output_path, summary) VALUES (?, ?, ?)",
            (job_id, output_path, summary),
        )
        return int(cursor.lastrowid)


def create_qa_pack(job_id: int | None, source_path: str | None = None, output_path: str | None = None, db_path: Path | None = None) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO qa_packs (job_id, source_path, output_path) VALUES (?, ?, ?)",
            (job_id, source_path, output_path),
        )
        return int(cursor.lastrowid)


def create_interview_prep_pack(
    output_path: str,
    question_count: int,
    job_id: int | None = None,
    resume_version_id: int | None = None,
    qa_pack_id: int | None = None,
    db_path: Path | None = None,
) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO interview_prep_packs
              (job_id, resume_version_id, qa_pack_id, output_path, question_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, resume_version_id, qa_pack_id, output_path, question_count),
        )
        return int(cursor.lastrowid)


def create_session(kind: str, status: str = "created", output_path: str | None = None, db_path: Path | None = None) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (kind, status, output_path) VALUES (?, ?, ?)",
            (kind, status, output_path),
        )
        return int(cursor.lastrowid)


def update_session_status(session_id: int, status: str, db_path: Path | None = None) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE sessions SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )


def get_row(table: str, row_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    allowed = {"jobs", "resume_versions", "applications", "qa_packs", "interview_prep_packs", "sessions", "events"}
    if table not in allowed:
        raise ValueError(f"Unsupported table: {table}")
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    return dict(row) if row else None


def tracking_summary(db_path: Path | None = None, limit: int = 5) -> dict[str, Any]:
    init_db(db_path)
    tables = ["jobs", "resume_versions", "interview_prep_packs", "sessions", "events"]
    with connect(db_path) as conn:
        counts = {
            table: int(conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
            for table in tables
        }
        recent_jobs = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, title, company, fit_score, status, created_at
                FROM jobs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        recent_resume_versions = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, job_id, output_path, summary, created_at
                FROM resume_versions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        recent_sessions = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, kind, status, output_path, created_at
                FROM sessions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        recent_events = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, run_id, stage, message, created_at
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
    return {
        "counts": counts,
        "recent_jobs": recent_jobs,
        "recent_resume_versions": recent_resume_versions,
        "recent_sessions": recent_sessions,
        "recent_events": recent_events,
    }
