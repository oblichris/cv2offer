# Test Cases

These test cases define the MVP quality bar for `cv2offer`. Automated coverage lives in `tests/`; browser-facing checks can be verified manually or moved into Playwright as the UI matures.

## Test Scope

The MVP must prove:

- The three worker boundaries stay decoupled.
- `jd_resume` and `interview_prep` run in-process through service calls.
- `interview_copilot` is the only worker that may use `process_manager.py`.
- Generated resume outputs can be promoted into editable active context files.
- Interview preparation reads from `context/`, not directly from resume output files.
- SQLite records outputs and progress.
- The HTML frontend can enter the major workflows independently.

## Test Environment Rules

- File-writing tests must use pytest's `tmp_path` fixture.
- In tests, point `CONTEXT_DIR`, `OUTPUT_DIR`, and `CV2OFFER_DB_PATH` to temporary paths.
- Tests must not write to the real project `context/`, `outputs/`, or `server/db/cv2offer.sqlite`.
- Default automated tests should set `CV2OFFER_MOCK=1`.
- Provider integration tests may use real API keys, but they must be opt-in and separate from default local/CI tests.
- Mock interview prep output must be deterministic: exactly 5 numbered questions in MVP mock mode.

## Unit Test Cases

### TC-U001: Context Promotion Writes Active Files

Target:

```text
server/services/context_service.py
```

Given:

- A source JD file exists.
- A generated resume file exists in `outputs/resumes/`.
- A QA source path is optional.

When:

- The user selects "Set as active context".

Then:

- `context/active_jd.md` is written.
- `context/active_resume.md` is written.
- `context/active_qa.md` is written only when QA exists or is intentionally initialized.
- `context/active_context.json` is written.
- `active_context.json` includes `source_jd_path`, `source_resume_path`, `source_qa_path`, active file paths, and `promoted_at`.

### TC-U002: Context Promotion Does Not Mutate Generated Output

Target:

```text
server/services/context_service.py
```

Given:

- A generated resume exists at `outputs/resumes/sample_resume_tailoring.md`.

When:

- The generated resume is promoted into `context/active_resume.md`.
- The user edits `context/active_resume.md`.

Then:

- `outputs/resumes/sample_resume_tailoring.md` remains unchanged.
- `context/active_resume.md` contains the user's edited content.

### TC-U003: SQLite Initializes Required Tables

Target:

```text
server/services/sqlite_service.py
server/db/schema.sql
```

Given:

- No local SQLite database exists.

When:

- The SQLite service initializes the database.

Then:

- These tables exist: `jobs`, `resume_versions`, `applications`, `qa_packs`, `interview_prep_packs`, `sessions`, `events`.
- The service can insert and read at least one event row.

### TC-U004: SQLite Records Events In Stage Order

Target:

```text
server/services/sqlite_service.py
server/db/schema.sql
```

Given:

- A fresh temporary SQLite database.

When:

- The app records progress events for a JD resume run.

Then:

- Events are queryable by run/session id.
- Events preserve stage order.
- The expected mock-stage order is exactly: `jd_parse`, `fit_score`, `resume_write`.
- The UI stream can read events in that same order.

### TC-U005: Provider Config Loads From Env

Target:

```text
server/services/llm_service.py
server/services/asr_service.py
server/services/tts_service.py
```

Given:

- Environment variables are loaded from `.env`.
- `CV2OFFER_MOCK=1` for default automated tests.

When:

- Each provider service initializes.

Then:

- LLM configuration is read from `LLM_PROVIDER` and related provider variables.
- ASR configuration is read from `ASR_PROVIDER` and related provider variables.
- TTS configuration is read from `TTS_PROVIDER` and related provider variables.
- Missing API keys produce clear errors without crashing the whole app at import time.
- When `CV2OFFER_MOCK=1`, services do not make network calls even if API keys are present.

## Worker Test Cases

### TC-W001: JD Resume Worker Produces Resume Output

Target:

```text
server/workers/jd_resume/service.py
```

Given:

- Resume text.
- JD text.

When:

- The worker runs a sample `generate_resume_tailoring` flow.

Then:

- A Markdown output is created in `outputs/resumes/`.
- The worker writes a `jobs` record and it is queryable.
- The worker writes a `resume_versions` record and it is queryable.
- The response includes output path, fit summary, and next action.

### TC-W002: Interview Prep Reads Active Context

Target:

```text
server/workers/interview_prep/service.py
```

Given:

- `context/active_jd.md` exists.
- `context/active_resume.md` exists.
- `context/active_qa.md` exists.

When:

- The worker generates an interview prep pack.

Then:

- The worker reads the three active context files.
- A Markdown file is created in `outputs/interview_50q/`.
- In `CV2OFFER_MOCK=1`, the output contains exactly 5 numbered questions.
- In real provider mode, the output contains exactly 50 numbered questions.
- The worker writes an `interview_prep_packs` record and it is queryable.

### TC-W003: Interview Prep Fails Clearly Without Context

Target:

```text
server/workers/interview_prep/service.py
```

Given:

- One or more active context files are missing.

When:

- The worker starts interview prep.

Then:

- The worker returns a clear error naming the missing file.
- It does not silently fall back to stale output files.
- It does not create a misleading interview pack.

### TC-W004: Interview Prep Does Not Read Generated Outputs

Target:

```text
server/workers/interview_prep/service.py
```

Given:

- A generated resume has been promoted into `context/active_resume.md`.
- `context/active_jd.md`, `context/active_resume.md`, and `context/active_qa.md` exist.
- The original generated resume file in `outputs/resumes/` is deleted or renamed after promotion.

When:

- The worker generates an interview prep pack.

Then:

- The worker still succeeds.
- The output reflects `context/active_resume.md`.
- The worker does not require the original `outputs/resumes/` file after promotion.

### TC-W005: Copilot Worker Is Process-Managed

Target:

```text
server/process_manager.py
server/workers/interview_copilot/
```

Given:

- The copilot worker is a long-running process or stub.

When:

- The app requests start, status, and stop.

Then:

- `process_manager.py` records process status.
- Stop is idempotent.
- `jd_resume` and `interview_prep` are not routed through PID management in the MVP.

## Integration Test Cases

### TC-I001: Resume To Interview Prep Flow

Given:

- A sample JD.
- A sample resume.

When:

1. Run the JD resume worker.
2. Promote the generated resume as active context.
3. Run the interview prep worker.

Then:

- `outputs/resumes/` contains the resume-tailoring output.
- `context/active_resume.md` matches the promoted resume content.
- `context/active_context.json` records the source resume path.
- `outputs/interview_50q/` contains the interview-prep output.
- SQLite has records for job, resume version, interview prep pack, and events.

### TC-I002: User Can Manually Edit Active Context

Given:

- A generated resume has been promoted to `context/active_resume.md`.

When:

- The user edits `context/active_resume.md`.
- The interview prep worker runs.

Then:

- The interview prep output reflects the edited active resume.
- The original generated resume output remains unchanged.

### TC-I003: No Provider Call In Mock Mode

Given:

- `CV2OFFER_MOCK=1`.
- API keys may be missing or present.

When:

- The JD resume worker or interview prep worker runs.

Then:

- The app still generates deterministic placeholder outputs.
- The interview prep placeholder output contains exactly 5 numbered questions.
- SQLite still records progress.
- The frontend can still demonstrate the product loop.

## Frontend Acceptance Cases

### TC-F001: Frontend Shows Three Independent Entries

Target:

```text
web/index.html
```

Given:

- The backend is running at `http://localhost:8765`.

When:

- The user opens the page in Chrome.

Then:

- The page shows entries for JD scan/resume tailoring, interview preparation, and live copilot.
- The user can start JD scan without starting copilot.
- The user can start interview preparation without starting copilot.

### TC-F002: Frontend Streams Progress

Given:

- The backend has a mocked stream endpoint.

When:

- The user runs a sample flow.

Then:

- The frontend shows progress messages in order.
- The final message includes generated output paths.

### TC-F003: Set Active Context Button

Given:

- A generated resume output exists.

When:

- The user clicks "Set as active context".

Then:

- The UI confirms the active context was updated.
- The UI shows paths for active JD, active resume, and active context metadata.

## Manual Smoke Test

Run after the first skeleton is built:

```bash
python3 server/app.py
```

Open:

```text
http://localhost:8765
```

Expected:

- The page loads.
- A sample JD/resume run completes.
- `outputs/resumes/` has one Markdown file.
- "Set as active context" writes `context/active_context.json`.
- Interview prep generates one Markdown file in `outputs/interview_50q/`.
- SQLite has visible rows for the run.

## First Pytest Targets

Once code exists, implement these first:

```text
tests/test_context_service.py
tests/test_sqlite_service.py
tests/test_jd_resume_worker.py
tests/test_interview_prep_worker.py
tests/test_process_manager.py
```

Do not test real DeepSeek, Stepfun ASR, or Stepfun TTS in default local tests. Mock provider calls unless running an explicit provider integration suite.
