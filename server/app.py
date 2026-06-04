from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.config import get_settings
from server.events import sse_lines
from server.process_manager import manager
from server.services import context_service, runtime_checks, sqlite_service
from server.workers.interview_copilot.service import (
    copilot_output_path,
    create_stub_session,
    read_copilot_events,
)
from server.workers.interview_prep.models import InterviewAnswerRequest, InterviewPrepRequest, InterviewSessionStartRequest
from server.workers.interview_prep.service import generate_interview_prep, start_interview_session, submit_interview_answer
from server.workers.jd_resume.models import JDResumeRequest
from server.workers.jd_resume.service import generate_resume_tailoring


class PromoteRequest(BaseModel):
    source_jd_path: str
    source_resume_path: str
    source_qa_path: str | None = None
    job_id: int | None = None
    resume_version_id: int | None = None
    qa_pack_id: int | None = None


class ActiveContextUpdateRequest(BaseModel):
    jd: str
    resume: str
    qa: str


def ensure_runtime_dirs() -> None:
    settings = get_settings()
    sqlite_service.init_db(settings.db_path)
    (settings.output_dir / "jds").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "resumes").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "interview_50q").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "sessions").mkdir(parents=True, exist_ok=True)
    settings.context_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ensure_runtime_dirs()
    yield


app = FastAPI(title="cv2offer", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str | int]:
    settings = get_settings()
    return {"status": "ok", "port": settings.port, "mock": str(settings.mock)}


@app.get("/api/runtime/checks")
def runtime_checks_endpoint():
    return runtime_checks.runtime_readiness()


@app.get("/api/tracking/summary")
def tracking_summary():
    return sqlite_service.tracking_summary()


@app.post("/api/jd-resume")
def run_jd_resume(request: JDResumeRequest):
    return generate_resume_tailoring(request).model_dump()


@app.post("/api/context/promote")
def promote_context(request: PromoteRequest):
    try:
        return context_service.promote_active_context(**request.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/context/active")
def active_context():
    settings = get_settings()
    exists = settings.active_context_path.exists()
    if not exists:
        return {"exists": False}
    try:
        context = context_service.read_active_context(settings)
    except FileNotFoundError as exc:
        return {"exists": False, "error": str(exc)}
    return {
        "exists": True,
        "jd": context["jd"],
        "resume": context["resume"],
        "qa": context["qa"],
        "metadata": context["metadata"],
        "paths": context["paths"],
    }


@app.put("/api/context/active")
def update_active_context(request: ActiveContextUpdateRequest):
    context = context_service.update_active_context(request.jd, request.resume, request.qa)
    return {
        "exists": True,
        "jd": context["jd"],
        "resume": context["resume"],
        "qa": context["qa"],
        "metadata": context["metadata"],
        "paths": context["paths"],
    }


@app.post("/api/interview-prep")
def run_interview_prep(request: InterviewPrepRequest | None = None):
    try:
        return generate_interview_prep(request or InterviewPrepRequest()).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/interview-prep/session/start")
def start_interactive_interview_prep(request: InterviewSessionStartRequest | None = None):
    try:
        return start_interview_session(request or InterviewSessionStartRequest()).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/interview-prep/session/answer")
def answer_interactive_interview_prep(request: InterviewAnswerRequest):
    try:
        return submit_interview_answer(request).model_dump()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/files/audio")
def get_audio(path: str):
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = ROOT / file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing audio file: {file_path}")
    media_type = "audio/mpeg" if file_path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(file_path, media_type=media_type)


@app.get("/api/events/{run_id}")
def get_events(run_id: str):
    return {"events": sqlite_service.get_events(run_id)}


@app.get("/api/events/{run_id}/stream")
def stream_events(run_id: str):
    events = sqlite_service.get_events(run_id)
    return StreamingResponse(sse_lines(events), media_type="text/event-stream")


@app.post("/api/copilot/session")
def copilot_session():
    return create_stub_session()


@app.post("/api/copilot/start")
def copilot_start():
    command = [sys.executable, "-m", "server.workers.interview_copilot.main"]
    output_path = copilot_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("", encoding="utf-8")
    state = manager.start("interview_copilot", command, cwd=ROOT, env={"COPILOT_OUTPUT_PATH": str(output_path)})
    return {**state.__dict__, "output_path": str(output_path)}


@app.get("/api/copilot/status")
def copilot_status():
    state = manager.status("interview_copilot")
    return {**state.__dict__, "events": read_copilot_events()[-20:]}


@app.post("/api/copilot/stop")
def copilot_stop():
    return manager.stop("interview_copilot").__dict__


@app.get("/api/copilot/events")
def copilot_events():
    return {"events": read_copilot_events()}


@app.get("/api/copilot/events/stream")
async def stream_copilot_event_log(request: Request):
    async def event_generator():
        seen = 0
        while not await request.is_disconnected():
            events = read_copilot_events()
            for event in events[seen:]:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            seen = len(events)
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("server.app:app", host=settings.host, port=settings.port, reload=False)
