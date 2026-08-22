import threading

from voice_assistant.recognizer import RecognitionResult
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


def test_worker_controls_queue_remote_audio_until_worker_completes_it() -> None:
    controls = WorkerControls()
    results = []

    thread = threading.Thread(
        target=lambda: results.append(
            controls.transcribe_remote_audio(b"\x00\x00" * 800, 16_000, 1)
        )
    )
    thread.start()
    request = controls.remote_audio_requests.get(timeout=1)
    request.result = RecognitionResult("გახსენი სთიმი", 1.0)
    request.completed.set()
    thread.join(timeout=1)

    assert results == [RecognitionResult("გახსენი სთიმი", 1.0)]
