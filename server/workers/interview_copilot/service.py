from __future__ import annotations

import json
import time
from datetime import datetime
from collections.abc import Iterable
from pathlib import Path
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.services import sqlite_service
from server.services.context_service import read_active_context
from server.services.llm_service import generate_answer_hint


def copilot_output_path() -> Path:
    settings = get_settings()
    settings.output_dir.joinpath("sessions").mkdir(parents=True, exist_ok=True)
    return settings.output_dir / "sessions" / "copilot_live.ndjson"


def create_stub_session() -> dict[str, str | int]:
    session_id = sqlite_service.create_session(kind="copilot", status="stub")
    return {"status": "stub", "message": "Live copilot is reserved for process-managed implementation.", "session_id": session_id}


def write_copilot_event(output_path: Path, event_type: str, text: str, hint: str | None = None) -> dict:
    event = {
        "type": event_type,
        "text": text,
        "hint": hint,
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_copilot_events(output_path: Path | None = None) -> list[dict]:
    output_path = output_path or copilot_output_path()
    if not output_path.exists():
        return []
    events = []
    for line in output_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def stream_copilot_events(
    output_path: Path | None = None,
    poll_seconds: float = 1.0,
    max_events: int | None = None,
) -> Iterable[str]:
    output_path = output_path or copilot_output_path()
    seen = 0
    sent = 0
    while True:
        events = read_copilot_events(output_path)
        for event in events[seen:]:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            sent += 1
            if max_events is not None and sent >= max_events:
                return
        seen = len(events)
        time.sleep(poll_seconds)


def answer_from_active_context(question: str) -> str:
    context = read_active_context()
    payload = {"jd": context["jd"], "resume": context["resume"], "qa": context["qa"]}
    hint = generate_answer_hint(question, payload).strip()
    if hint:
        return hint
    fallback_question = "请基于当前JD、简历和QA，给出一个可直接开口的面试回答提示。"
    hint = generate_answer_hint(fallback_question, payload).strip()
    if hint:
        return hint
    return (
        "可以按三段回答：先说明你会把模糊需求拆成业务流程和关键约束，"
        "再结合简历中的咨询和 AI workflow 项目说明如何做 MVP 验证，"
        "最后补充用时间节省、准确率或业务采纳度衡量效果。"
    )
