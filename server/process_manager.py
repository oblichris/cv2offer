from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessState:
    name: str
    pid: int | None
    status: str
    returncode: int | None = None


class ProcessManager:
    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen] = {}

    def start(self, name: str, command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> ProcessState:
        existing = self._processes.get(name)
        if existing and existing.poll() is None:
            return ProcessState(name=name, pid=existing.pid, status="running")
        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        process = subprocess.Popen(command, cwd=cwd, env=child_env)
        self._processes[name] = process
        return ProcessState(name=name, pid=process.pid, status="running")

    def status(self, name: str) -> ProcessState:
        process = self._processes.get(name)
        if not process:
            return ProcessState(name=name, pid=None, status="stopped")
        status = "running" if process.poll() is None else "stopped"
        return ProcessState(name=name, pid=process.pid, status=status, returncode=process.returncode)

    def stop(self, name: str, timeout: float = 3.0) -> ProcessState:
        process = self._processes.get(name)
        if not process:
            return ProcessState(name=name, pid=None, status="stopped")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout)
        return ProcessState(name=name, pid=process.pid, status="stopped", returncode=process.returncode)


manager = ProcessManager()
