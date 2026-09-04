from voice_assistant import mcu_face


def test_worker_statuses_map_to_semantic_face_states() -> None:
    assert mcu_face.state_for_status("sleeping") == "IDLE"
    assert mcu_face.state_for_status("listening_command") == "LISTEN"
    assert mcu_face.state_for_status("executing") == "THINK"
    assert mcu_face.state_for_status("recovering_audio") == "ERROR"


def test_response_events_map_to_outcome_states() -> None:
    assert mcu_face.state_for_response("launch_success") == "SUCCESS"
    assert mcu_face.state_for_response("already_running") == "SUCCESS"
    assert mcu_face.state_for_response("launch_failed") == "ERROR"
    assert mcu_face.state_for_response("command_not_understood") == "ERROR"
    assert mcu_face.state_for_response("ready") == "LISTEN"
    assert mcu_face.state_for_response("startup_ready") == "TALK"


def test_board_discovery_uses_stable_usb_identity(monkeypatch) -> None:
    ports = [
        type("Port", (), {"device": "COM9", "vid": 0x1234, "pid": 0x5678})(),
        type("Port", (), {"device": "COM4", "vid": mcu_face.BOARD_VID, "pid": mcu_face.BOARD_PID})(),
    ]
    monkeypatch.setattr(mcu_face.list_ports, "comports", lambda: ports)

    assert mcu_face.find_board_port() == "COM4"
