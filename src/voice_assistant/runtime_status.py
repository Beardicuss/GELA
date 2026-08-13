from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading

from .config import USER_DATA_ROOT
from .storage import atomic_write_text


STATUS_PATH = USER_DATA_ROOT / "runtime" / "status.json"


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
