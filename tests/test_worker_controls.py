from voice_assistant.worker import WorkerControls


def test_worker_controls_publish_status_changes_once() -> None:
    changes: list[str] = []
    controls = WorkerControls(changes.append)
    controls.set_status("sleeping")
    controls.set_status("sleeping")
    controls.set_status("paused")
    assert changes == ["sleeping", "paused"]
    assert controls.status == "paused"


def test_worker_control_events_default_to_clear() -> None:
    controls = WorkerControls()
    assert not controls.stop_event.is_set()
    assert not controls.pause_event.is_set()
    assert not controls.reload_event.is_set()
    assert not controls.release_audio_event.is_set()


def test_worker_controls_support_multiple_status_observers() -> None:
    first: list[str] = []
    second: list[str] = []
    controls = WorkerControls(first.append)
    controls.add_status_callback(second.append)

    controls.set_status("sleeping")

    assert first == ["sleeping"]
    assert second == ["sleeping"]


def test_worker_controls_publish_safe_microphone_release_reason() -> None:
    controls = WorkerControls()

    controls.request_audio_release("recognition_testing")

    assert controls.release_audio_event.is_set()
    assert controls.audio_release_reason == "recognition_testing"
