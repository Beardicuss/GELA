from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import threading

from .config import USER_DATA_ROOT
from .storage import atomic_write_text


STATUS_PATH = USER_DATA_ROOT / "runtime" / "status.json"
WORKER_HEARTBEAT_PATH = USER_DATA_ROOT / "runtime" / "worker_heartbeat.json"


class WorkerHeartbeat:
    """Small liveness marker, separate from the worker's last status snapshot."""

    def __init__(self, path: Path = WORKER_HEARTBEAT_PATH, interval_seconds: float = 2.0) -> None:
        self.path = path
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _write(self) -> None:
        try:
            atomic_write_text(
                self.path,
                json.dumps({"pid": os.getpid(), "updated_at": datetime.now().astimezone().isoformat()}) + "\n",
            )
        except OSError:
            # Diagnostics must never stop the voice worker.
            pass

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._write()
        thread = threading.Thread(target=self._run, name="gela-worker-heartbeat", daemon=True)
        thread.start()
        self._thread = thread

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._write()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1)
            self._thread = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


class RuntimeStatusStore:
    def __init__(self, path: Path = STATUS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._state: dict[str, object] = {
            "status": "starting",
            "microphone": "Checking…",
            "microphone_state": "starting",
            "models": "Loading…",
            "catalog": "Loading…",
            "last_wake": "None yet",
            "last_command": "None yet",
            "last_execution": "None yet",
        }

    def update(self, **values: object) -> None:
        with self._lock:
            self._state.update(values)
            self._state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            atomic_write_text(
                self.path,
                json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
            )


def read_runtime_status(path: Path = STATUS_PATH) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
