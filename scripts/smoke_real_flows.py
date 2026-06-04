from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import get_settings
from server.services import sqlite_service
from server.services.asr_service import transcribe_audio_base64
from server.services.context_service import read_active_context
from server.services.llm_service import generate_answer_hint
from server.services.runtime_checks import runtime_readiness
from server.services.tts_service import synthesize_speech
from server.workers.interview_copilot.main import CAPTURE_RATE, capture_segment, find_blackhole_device, pcm_to_wav_base64
from server.workers.interview_prep.models import InterviewAnswerRequest, InterviewSessionStartRequest
from server.workers.interview_prep.service import start_interview_session, submit_interview_answer


def ensure_real_ready(kind: str) -> dict:
    checks = runtime_readiness()
    if kind == "interview-prep" and not checks["ready_for_real_interview_prep"]:
        raise RuntimeError("Real interview prep is not ready. Configure DeepSeek and Stepfun keys with CV2OFFER_MOCK=0.")
    if kind == "copilot" and not checks["ready_for_real_copilot"]:
        raise RuntimeError("Real copilot is not ready. Configure keys, set CV2OFFER_MOCK=0, and expose BlackHole input.")
    return checks


def run_interview_prep_smoke(answer_text: str) -> dict:
    ensure_real_ready("interview-prep")
    settings = get_settings()
    sqlite_service.init_db(settings.db_path)
    read_active_context(settings)

    started = start_interview_session(InterviewSessionStartRequest(question_count=1), settings=settings)
    answer_audio = synthesize_speech(answer_text)
    answer_audio_base64 = base64.b64encode(answer_audio).decode("ascii")
    mime_type = "audio/wav" if settings.mock else "audio/mp3"
    answered = submit_interview_answer(
        InterviewAnswerRequest(
            run_id=started.run_id,
            question_index=started.question_index,
            audio_base64=answer_audio_base64,
            audio_mime_type=mime_type,
        ),
        settings=settings,
    )

    return {
        "mode": "interview-prep",
        "run_id": answered.run_id,
        "session_id": answered.session_id,
        "question": answered.question,
        "question_audio_path": started.audio_path,
        "transcript": answered.transcript,
        "feedback_preview": answered.feedback[:300],
        "session_path": answered.session_path,
    }


def find_blackhole_output_device() -> int:
    import sounddevice as sd

    preferred_name = os.getenv("COPILOT_AUDIO_DEVICE", "BlackHole")
    for index, device in enumerate(sd.query_devices()):
        if preferred_name.lower() in device["name"].lower() and int(device.get("max_output_channels", 0)) > 0:
            return index
    raise RuntimeError(f"{preferred_name} output device not found.")


def make_system_voice_wav(text: str) -> Path:
    temp = tempfile.NamedTemporaryFile(prefix="cv2offer_copilot_", suffix=".wav", delete=False)
    temp.close()
    path = Path(temp.name)
    subprocess.run(
        ["say", "--file-format=WAVE", "--data-format=LEI16@16000", "-o", str(path), text],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def read_wav_float32(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
    if channels > 1:
        data = data.reshape(-1, channels)
    return data, sample_rate


def capture_segment_with_test_audio(text: str) -> np.ndarray:
    import sounddevice as sd

    wav_path = make_system_voice_wav(text)
    try:
        audio, sample_rate = read_wav_float32(wav_path)
        output_device = find_blackhole_output_device()
        input_device = find_blackhole_device()
        if audio.ndim > 1:
            audio = audio[:, 0]
        target_len = int(len(audio) * CAPTURE_RATE / sample_rate)
        playback = np.interp(np.linspace(0, len(audio) - 1, target_len), np.arange(len(audio)), audio).astype(np.float32)
        pad = np.zeros(int(CAPTURE_RATE * 0.5), dtype=np.float32)
        playback = np.concatenate([pad, playback, pad])
        recording = sd.playrec(
            playback.reshape(-1, 1),
            samplerate=CAPTURE_RATE,
            channels=1,
            dtype="float32",
            device=(input_device, output_device),
        )
        sd.wait()
        mono = recording[:, 0]
        target_len = int(len(mono) * 16000 / CAPTURE_RATE)
        resampled = np.interp(np.linspace(0, len(mono) - 1, target_len), np.arange(len(mono)), mono)
        return (resampled * 32767).astype(np.int16)
    finally:
        wav_path.unlink(missing_ok=True)


def run_copilot_smoke(min_rms: float, inject_test_audio: bool, test_question: str) -> dict:
    ensure_real_ready("copilot")
    context = read_active_context()
    pcm = capture_segment_with_test_audio(test_question) if inject_test_audio else capture_segment()
    if pcm.size == 0:
        raise RuntimeError("Captured empty BlackHole audio segment.")
    rms = float((pcm.astype("float32") ** 2).mean() ** 0.5)
    if rms < min_rms:
        raise RuntimeError(f"Captured BlackHole audio is too quiet for ASR smoke: rms={rms:.0f}, min_rms={min_rms:.0f}.")
    transcript = transcribe_audio_base64(pcm_to_wav_base64(pcm), "audio/wav")
    if not transcript:
        raise RuntimeError("ASR returned an empty transcript.")
    hint = generate_answer_hint(transcript, {"jd": context["jd"], "resume": context["resume"], "qa": context["qa"]})
    return {
        "mode": "copilot",
        "injected_test_audio": inject_test_audio,
        "rms": round(rms, 2),
        "transcript": transcript,
        "hint_preview": hint[:300],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run opt-in real-provider smoke checks for cv2offer.")
    parser.add_argument("--mode", choices=["interview-prep", "copilot"], required=True)
    parser.add_argument(
        "--answer-text",
        default="我会先拆解客户业务流程，识别高价值 AI 场景，再用 MVP 快速验证效果。",
        help="Text to synthesize as a mock candidate answer for the real interview-prep smoke.",
    )
    parser.add_argument(
        "--test-question",
        default="请介绍一下你如何把模糊的企业需求转成一个可以验证的 AI 工作流 MVP。",
        help="Question spoken into BlackHole for the real copilot smoke.",
    )
    parser.add_argument("--no-inject-test-audio", action="store_true", help="Capture existing BlackHole audio instead of injecting a test question.")
    parser.add_argument("--min-rms", type=float, default=80.0, help="Minimum BlackHole RMS for copilot ASR smoke.")
    args = parser.parse_args()

    try:
        if args.mode == "interview-prep":
            result = run_interview_prep_smoke(args.answer_text)
        else:
            result = run_copilot_smoke(args.min_rms, not args.no_inject_test_audio, args.test_question)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
