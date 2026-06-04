const logEl = document.querySelector("#log");
const promoteBtn = document.querySelector("#promoteBtn");
const prepBtn = document.querySelector("#prepBtn");
const startCoachBtn = document.querySelector("#startCoachBtn");
const submitAnswerBtn = document.querySelector("#submitAnswerBtn");
const resumeStatus = document.querySelector("#resumeStatus");
const contextStatus = document.querySelector("#contextStatus");
const coachQuestion = document.querySelector("#coachQuestion");
const questionAudio = document.querySelector("#questionAudio");
const answerText = document.querySelector("#answerText");
const coachFeedback = document.querySelector("#coachFeedback");
const copilotLog = document.querySelector("#copilotLog");
const recordBtn = document.querySelector("#recordBtn");
const stopRecordBtn = document.querySelector("#stopRecordBtn");
const recordStatus = document.querySelector("#recordStatus");
const activeJdText = document.querySelector("#activeJdText");
const activeResumeText = document.querySelector("#activeResumeText");
const activeQaText = document.querySelector("#activeQaText");
const saveContextBtn = document.querySelector("#saveContextBtn");
const saveContextStatus = document.querySelector("#saveContextStatus");
const refreshTrackingBtn = document.querySelector("#refreshTrackingBtn");
const trackingSummary = document.querySelector("#trackingSummary");
let lastResumeResult = null;
let activeContext = null;
let coachSession = null;
let copilotTimer = null;
let copilotSource = null;
let copilotEvents = [];
let mediaRecorder = null;
let recordedChunks = [];
let recordedAudioBase64 = null;
let recordedAudioMimeType = "audio/ogg";

const sampleJd = `AI Product Manager

Responsibilities:
- Discover user pain points in AI-assisted productivity and workflow automation.
- Define PRDs, MVP scope, success metrics, and product roadmap for LLM features.
- Work with design, engineering, data, and GTM teams to validate AI product experiments.
- Use user feedback, funnel data, and adoption metrics to iterate product direction.`;

const sampleResume = `Product-minded builder with experience in user research, AI workflow prototyping, product requirement definition, and local full-stack MVP delivery. Built cv2offer, an AI job-search product with HTML frontend, Python backend, SQLite tracking, TTS/ASR coaching, and live copilot hints.`;

document.querySelector("#jdText").value = sampleJd;
document.querySelector("#resumeText").value = sampleResume;

function log(value) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const time = new Date().toLocaleTimeString();
  logEl.textContent = `${logEl.textContent}${time}\n${text}\n\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText);
  }
  return payload;
}

document.querySelector("#healthBtn").addEventListener("click", async () => {
  try {
    log(await request("/api/health"));
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#runtimeCheckBtn").addEventListener("click", async () => {
  try {
    log(await request("/api/runtime/checks"));
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#runJdBtn").addEventListener("click", async () => {
  const payload = {
    jd_text: document.querySelector("#jdText").value,
    resume_text: document.querySelector("#resumeText").value,
    title: "Sample AI Product Manager",
  };
  try {
    resumeStatus.textContent = "Running JD resume worker...";
    promoteBtn.disabled = true;
    prepBtn.disabled = true;
    lastResumeResult = await request("/api/jd-resume", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    promoteBtn.disabled = false;
    resumeStatus.textContent = `Resume output ready: ${lastResumeResult.output_path}`;
    log(lastResumeResult);
    await refreshTracking();
  } catch (error) {
    resumeStatus.textContent = "JD resume worker failed.";
    log(`Error: ${error.message}`);
  }
});

promoteBtn.addEventListener("click", async () => {
  if (!lastResumeResult) return;
  const payload = {
    source_jd_path: lastResumeResult.jd_output_path,
    source_resume_path: lastResumeResult.output_path,
    source_qa_path: "examples/sample-qa.md",
    job_id: lastResumeResult.job_id,
    resume_version_id: lastResumeResult.resume_version_id,
  };
  try {
    const result = await request("/api/context/promote", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    log(result);
    await refreshActiveContext();
    await refreshTracking();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

async function refreshActiveContext() {
  activeContext = await request("/api/context/active");
  if (activeContext.exists) {
    const source = activeContext.metadata?.source_resume_path || "unknown resume";
    contextStatus.textContent = `Active context ready: ${source}`;
    prepBtn.disabled = false;
    startCoachBtn.disabled = false;
    activeJdText.value = activeContext.jd || "";
    activeResumeText.value = activeContext.resume || "";
    activeQaText.value = activeContext.qa || "";
    saveContextBtn.disabled = false;
    saveContextStatus.textContent = "Active context loaded. Edits here affect coaching and copilot.";
  } else {
    contextStatus.textContent = activeContext.error || "No active context. Run JD resume worker, then set active context.";
    prepBtn.disabled = true;
    startCoachBtn.disabled = true;
    activeJdText.value = "";
    activeResumeText.value = "";
    activeQaText.value = "";
    saveContextBtn.disabled = true;
    saveContextStatus.textContent = "No active context to edit yet.";
  }
  log(activeContext);
}

saveContextBtn.addEventListener("click", async () => {
  try {
    saveContextStatus.textContent = "Saving active context...";
    const result = await request("/api/context/active", {
      method: "PUT",
      body: JSON.stringify({
        jd: activeJdText.value,
        resume: activeResumeText.value,
        qa: activeQaText.value,
      }),
    });
    activeContext = result;
    saveContextStatus.textContent = "Saved. Coaching and copilot will use these edited files.";
    log(result);
  } catch (error) {
    saveContextStatus.textContent = "Save failed.";
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#refreshContextBtn").addEventListener("click", async () => {
  try {
    await refreshActiveContext();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#prepBtn").addEventListener("click", async () => {
  try {
    await refreshActiveContext();
    if (!activeContext?.exists) return;
    log(await request("/api/interview-prep", {
      method: "POST",
      body: JSON.stringify({}),
    }));
    await refreshTracking();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

function setAudio(path) {
  questionAudio.src = `/api/files/audio?path=${encodeURIComponent(path)}`;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCoachFeedback(result) {
  coachFeedback.innerHTML = `
    <div class="feedback-block">
      <h3>Transcript</h3>
      <p>${escapeHtml(result.transcript)}</p>
    </div>
    <div class="feedback-block">
      <h3>Feedback</h3>
      <p>${escapeHtml(result.feedback)}</p>
    </div>
    <div class="feedback-block">
      <h3>Session</h3>
      <p>${escapeHtml(result.session_path)}</p>
    </div>
  `;
}

function renderTracking(payload) {
  const counts = payload.counts || {};
  const countCards = [
    ["Jobs", counts.jobs || 0],
    ["Resumes", counts.resume_versions || 0],
    ["Prep Packs", counts.interview_prep_packs || 0],
    ["Sessions", counts.sessions || 0],
    ["Events", counts.events || 0],
  ]
    .map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
  const jobs = (payload.recent_jobs || [])
    .map((job) => `<li><strong>${escapeHtml(job.title)}</strong><span>fit ${job.fit_score ?? "-"} / ${escapeHtml(job.status)}</span></li>`)
    .join("");
  const sessions = (payload.recent_sessions || [])
    .map((session) => `<li><strong>${escapeHtml(session.kind)}</strong><span>${escapeHtml(session.status)} / ${escapeHtml(session.output_path || "")}</span></li>`)
    .join("");
  const events = (payload.recent_events || [])
    .map((event) => `<li><strong>${escapeHtml(event.stage)}</strong><span>${escapeHtml(event.message)}</span></li>`)
    .join("");
  trackingSummary.innerHTML = `
    <div class="stats">${countCards}</div>
    <div class="tracking-lists">
      <div>
        <h3>Recent Jobs</h3>
        <ul>${jobs || "<li><span>No jobs yet.</span></li>"}</ul>
      </div>
      <div>
        <h3>Recent Sessions</h3>
        <ul>${sessions || "<li><span>No sessions yet.</span></li>"}</ul>
      </div>
      <div>
        <h3>Recent Events</h3>
        <ul>${events || "<li><span>No events yet.</span></li>"}</ul>
      </div>
    </div>
  `;
}

async function refreshTracking() {
  const payload = await request("/api/tracking/summary");
  renderTracking(payload);
  return payload;
}

document.querySelector("#startCoachBtn").addEventListener("click", async () => {
  try {
    await refreshActiveContext();
    if (!activeContext?.exists) return;
    coachSession = await request("/api/interview-prep/session/start", {
      method: "POST",
      body: JSON.stringify({}),
    });
    coachQuestion.textContent = `Q${coachSession.question_index}/${coachSession.question_count}: ${coachSession.question}`;
    setAudio(coachSession.audio_path);
    answerText.value = "";
    coachFeedback.innerHTML = '<p class="empty">Feedback will appear here after you submit an answer.</p>';
    submitAnswerBtn.disabled = false;
    recordBtn.disabled = !navigator.mediaDevices?.getUserMedia;
    recordedAudioBase64 = null;
    recordStatus.textContent = recordBtn.disabled ? "Browser recording is unavailable; type your answer." : "Ready to record, or type your answer.";
    log(coachSession);
    await refreshTracking();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

submitAnswerBtn.addEventListener("click", async () => {
  if (!coachSession) return;
  try {
    submitAnswerBtn.disabled = true;
    coachFeedback.innerHTML = '<p class="empty">Getting feedback...</p>';
    const payload = {
      run_id: coachSession.run_id,
      question_index: coachSession.question_index,
    };
    if (answerText.value.trim()) {
      payload.answer_text = answerText.value;
    } else if (recordedAudioBase64) {
      payload.audio_base64 = recordedAudioBase64;
      payload.audio_mime_type = recordedAudioMimeType;
    }
    const result = await request("/api/interview-prep/session/answer", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderCoachFeedback(result);
    log(result);
    await refreshTracking();
    if (result.next_question) {
      coachSession.question_index += 1;
      coachSession.question = result.next_question;
      coachQuestion.textContent = `Q${coachSession.question_index}/${coachSession.question_count}: ${result.next_question}`;
      setAudio(result.next_audio_path);
      answerText.value = "";
      recordedAudioBase64 = null;
      recordStatus.textContent = "Ready to record, or type your answer.";
      submitAnswerBtn.disabled = false;
    } else {
      coachQuestion.textContent = "Coaching session complete.";
      submitAnswerBtn.disabled = true;
    }
  } catch (error) {
    submitAnswerBtn.disabled = false;
    coachFeedback.innerHTML = `<p class="empty">Error: ${escapeHtml(error.message)}</p>`;
    log(`Error: ${error.message}`);
  }
});

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

recordBtn.addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const preferred = MediaRecorder.isTypeSupported("audio/ogg") ? "audio/ogg" : "";
    mediaRecorder = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined);
    recordedChunks = [];
    recordedAudioBase64 = null;
    recordedAudioMimeType = mediaRecorder.mimeType || "audio/ogg";
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.onstop = async () => {
      const blob = new Blob(recordedChunks, { type: recordedAudioMimeType });
      recordedAudioBase64 = await blobToBase64(blob);
      stream.getTracks().forEach((track) => track.stop());
      recordStatus.textContent = `Recorded ${Math.round(blob.size / 1024)} KB (${recordedAudioMimeType}). Submit to use ASR.`;
      recordBtn.disabled = false;
      stopRecordBtn.disabled = true;
    };
    mediaRecorder.start();
    recordStatus.textContent = "Recording... click Stop Recording when done.";
    recordBtn.disabled = true;
    stopRecordBtn.disabled = false;
  } catch (error) {
    recordStatus.textContent = `Recording failed: ${error.message}`;
  }
});

stopRecordBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
});

refreshTrackingBtn.addEventListener("click", async () => {
  try {
    log(await refreshTracking());
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

async function refreshCopilotEvents() {
  const payload = await request("/api/copilot/events");
  copilotEvents = payload.events;
  renderCopilotEvents();
}

function renderCopilotEvents() {
  copilotLog.textContent = copilotEvents
    .slice(-8)
    .map((event) => `${event.created_at} [${event.type}]\n${event.text}${event.hint ? `\nHint: ${event.hint}` : ""}`)
    .join("\n\n");
  copilotLog.scrollTop = copilotLog.scrollHeight;
}

function startCopilotStream() {
  if (copilotSource) copilotSource.close();
  if (!window.EventSource) {
    copilotTimer = setInterval(() => refreshCopilotEvents().catch(() => {}), 2000);
    return;
  }
  copilotSource = new EventSource("/api/copilot/events/stream");
  copilotSource.onmessage = (message) => {
    copilotEvents.push(JSON.parse(message.data));
    renderCopilotEvents();
  };
  copilotSource.onerror = () => {
    copilotSource.close();
    copilotSource = null;
    if (!copilotTimer) copilotTimer = setInterval(() => refreshCopilotEvents().catch(() => {}), 2000);
  };
}

function stopCopilotStream() {
  if (copilotSource) {
    copilotSource.close();
    copilotSource = null;
  }
  if (copilotTimer) {
    clearInterval(copilotTimer);
    copilotTimer = null;
  }
}

document.querySelector("#copilotStartBtn").addEventListener("click", async () => {
  try {
    log(await request("/api/copilot/start", { method: "POST" }));
    copilotEvents = [];
    startCopilotStream();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#copilotStatusBtn").addEventListener("click", async () => {
  try {
    const status = await request("/api/copilot/status");
    log(status);
    await refreshCopilotEvents();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

document.querySelector("#copilotStopBtn").addEventListener("click", async () => {
  try {
    log(await request("/api/copilot/stop", { method: "POST" }));
    stopCopilotStream();
    await refreshCopilotEvents();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

refreshActiveContext().catch(() => {
  contextStatus.textContent = "No active context. Run JD resume worker, then set active context.";
});

refreshTracking().catch(() => {});
