from voice_assistant.runtime_status import RuntimeStatusStore, read_runtime_status


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
