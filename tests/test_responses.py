from voice_assistant import responses
from voice_assistant.responses import VoiceResponses, response_event_for_detail


def test_stop_response_cancels_windows_playback(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(responses.winsound, "PlaySound", lambda sound, flags: calls.append((sound, flags)))

    VoiceResponses.stop()

    assert calls == [(None, 0)]


def test_state_details_select_reusable_response_events() -> None:
    assert response_event_for_detail("state already_running process=chrome") == "already_running"
    assert response_event_for_detail("state already_stopped app=Steam") == "already_stopped"
    assert response_event_for_detail("state already_on radio=WiFi") == "already_on"
    assert response_event_for_detail("state already_off radio=Bluetooth") == "already_off"
    assert response_event_for_detail("verified stable process=chrome") == "launch_success"


def test_recorded_voice_response_coverage_is_complete() -> None:
    assert VoiceResponses().coverage() == {"missing": [], "orphaned": []}
