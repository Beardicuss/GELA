import json
import os

from voice_assistant.runtime_status import RuntimeStatusStore, WorkerHeartbeat, read_runtime_status


def test_runtime_status_keeps_only_latest_values(tmp_path) -> None:
    path = tmp_path / "runtime" / "status.json"
    store = RuntimeStatusStore(path)

    store.update(status="sleeping", last_command="first")
    store.update(status="executing", last_command="second")
    state = read_runtime_status(path)

    assert state["status"] == "executing"
    assert state["last_command"] == "second"
    assert "first" not in path.read_text(encoding="utf-8")
    assert state["updated_at"]


def test_worker_heartbeat_is_separate_and_removed_on_stop(tmp_path) -> None:
    path = tmp_path / "runtime" / "worker_heartbeat.json"
    heartbeat = WorkerHeartbeat(path, interval_seconds=0.02)
    heartbeat.start()
    try:
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8"))["pid"] == os.getpid()
    finally:
        heartbeat.stop()
    assert not path.exists()
