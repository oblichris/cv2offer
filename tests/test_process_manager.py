from __future__ import annotations

import sys
import time

from server.process_manager import ProcessManager


def test_process_manager_start_status_stop(tmp_path):
    manager = ProcessManager()
    state = manager.start("copilot", [sys.executable, "-c", "import time; time.sleep(10)"], cwd=tmp_path)
    assert state.status == "running"
    assert state.pid is not None

    status = manager.status("copilot")
    assert status.status == "running"

    stopped = manager.stop("copilot")
    assert stopped.status == "stopped"
    assert stopped.returncode is not None
    time.sleep(0.1)
    assert manager.stop("copilot").status == "stopped"


def test_process_manager_kills_process_that_ignores_terminate(tmp_path):
    manager = ProcessManager()
    command = [
        sys.executable,
        "-c",
        "import signal, time; signal.signal(signal.SIGTERM, lambda *_: None); time.sleep(10)",
    ]
    state = manager.start("stubborn", command, cwd=tmp_path)
    assert state.status == "running"

    stopped = manager.stop("stubborn", timeout=0.1)

    assert stopped.status == "stopped"
    assert stopped.returncode is not None
