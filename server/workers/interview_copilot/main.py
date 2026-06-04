from __future__ import annotations

import base64
import os
import sys
import time
import wave
from io import BytesIO
from pathlib import Path

import numpy as np

from server.config import env_bool
from server.services.asr_service import transcribe_audio_base64
from server.workers.interview_copilot.service import answer_from_active_context, copilot_output_path, write_copilot_event


CAPTURE_RATE = 48000
ASR_RATE = 16000
CHANNELS = 1
DEFAULT_SEGMENT_SECONDS = 4


def output_path_from_env() -> Path:
    raw = os.getenv("COPILOT_OUTPUT_PATH")
    return Path(raw) if raw else copilot_output_path()


def mock_loop(output_path: Path) -> None:
    write_copilot_event(output_path, "status", "mock copilot started")
    samples = [
        "请介绍一下你过去做过的 AI 工作流项目。",
        "你为什么适合这个 AI 解决方案顾问岗位？",
        "如果客户需求很模糊，你会如何推进？",
    ]
    idx = 0
    while True:
        question = samples[idx % len(samples)]
        hint = answer_from_active_context(question)
        write_copilot_event(output_path, "question", question, hint)
        idx += 1
        time.sleep(5)


def find_blackhole_device(preferred_name: str | None = None) -> int:
    import sounddevice as sd

    preferred_name = preferred_name or os.getenv("COPILOT_AUDIO_DEVICE", "BlackHole")
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        if preferred_name.lower() in device["name"].lower() and device["max_input_channels"] > 0:
            return index
    raise RuntimeError(f"{preferred_name} input device not found. Install/configure BlackHole 2ch first.")


def pcm_to_wav_base64(pcm: np.ndarray, sample_rate: int = ASR_RATE) -> str:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.astype(np.int16).tobytes())
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def capture_segment() -> np.ndarray:
    import sounddevice as sd

    device = find_blackhole_device()
    segment_seconds = float(os.getenv("COPILOT_SEGMENT_SECONDS", str(DEFAULT_SEGMENT_SECONDS)))
    frames = int(CAPTURE_RATE * segment_seconds)
    audio = sd.rec(frames, samplerate=CAPTURE_RATE, channels=1, dtype="float32", device=device)
    sd.wait()
    mono = audio[:, 0]
    target_len = int(len(mono) * ASR_RATE / CAPTURE_RATE)
    resampled = np.interp(np.linspace(0, len(mono) - 1, target_len), np.arange(len(mono)), mono)
    return (resampled * 32767).astype(np.int16)


def real_loop(output_path: Path) -> None:
    write_copilot_event(output_path, "status", "real copilot started; listening to BlackHole system audio")
    silence_threshold = float(os.getenv("COPILOT_SILENCE_RMS_THRESHOLD", "80"))
    while True:
        pcm = capture_segment()
        rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2))) if pcm.size else 0
        if rms < silence_threshold:
            write_copilot_event(output_path, "status", f"silence/noise skipped rms={rms:.0f}")
            continue
        audio_base64 = pcm_to_wav_base64(pcm)
        transcript = transcribe_audio_base64(audio_base64, "audio/wav")
        if not transcript:
            continue
        hint = answer_from_active_context(transcript)
        write_copilot_event(output_path, "question", transcript, hint)


def main() -> None:
    output_path = output_path_from_env()
    try:
        if env_bool("CV2OFFER_MOCK", False):
            mock_loop(output_path)
        else:
            real_loop(output_path)
    except KeyboardInterrupt:
        write_copilot_event(output_path, "status", "copilot stopped")
    except Exception as exc:
        write_copilot_event(output_path, "error", str(exc))
        raise


if __name__ == "__main__":
    main()
