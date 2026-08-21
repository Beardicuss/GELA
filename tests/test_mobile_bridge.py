from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voice_assistant.mobile_bridge import DeviceStore, MobileBridgeService, PairingSession, create_handler
from voice_assistant.remote_commands import RemoteCommandResult


def request_json(base_url: str, path: str, *, method: str = "GET", body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def start_server(tmp_path: Path):
    pairing = PairingSession(ttl_seconds=60)
    devices = DeviceStore(tmp_path / "devices.json")
    executed = []

    def executor(transcript: str, language: str):
        executed.append((transcript, language))
        return RemoteCommandResult("executed", transcript, "Test command", "Done")

    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(pairing, devices, executor))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, pairing, devices, executed, f"http://127.0.0.1:{server.server_port}"


def test_pair_then_execute_authenticated_command(tmp_path):
    server, pairing, devices, executed, base_url = start_server(tmp_path)
    try:
        status, info = request_json(base_url, "/v1/info")
        assert status == 200
        assert info["service"] == "gela-pc-bridge"

        status, paired = request_json(
            base_url,
            "/v1/pair",
            method="POST",
            body={"protocolVersion": 1, "pairingCode": pairing.code},
        )
        assert status == 201
        assert devices.authenticate(paired["accessToken"])

        status, result = request_json(
            base_url,
            "/v1/commands/text",
            method="POST",
            token=paired["accessToken"],
            body={"protocolVersion": 1, "requestId": "request-1", "transcript": "ხმა აუწიე", "language": "ka"},
        )
        assert status == 200
        assert result["status"] == "executed"
        assert result["requestId"] == "request-1"
        assert executed == [("ხმა აუწიე", "ka")]
    finally:
        server.shutdown()
        server.server_close()


def test_rejects_bad_pairing_code_and_unauthenticated_command(tmp_path):
    server, _, _, executed, base_url = start_server(tmp_path)
    try:
        status, _ = request_json(
            base_url,
            "/v1/pair",
            method="POST",
            body={"protocolVersion": 1, "pairingCode": "000000"},
        )
        assert status == 401

        status, _ = request_json(
            base_url,
            "/v1/commands/text",
            method="POST",
            body={"protocolVersion": 1, "requestId": "request-2", "transcript": "volume up", "language": "en"},
        )
        assert status == 401
        assert executed == []
    finally:
        server.shutdown()
        server.server_close()


def test_pairing_code_is_one_time(tmp_path):
    server, pairing, _, _, base_url = start_server(tmp_path)
    body = {"protocolVersion": 1, "pairingCode": pairing.code}
    try:
        assert request_json(base_url, "/v1/pair", method="POST", body=body)[0] == 201
        assert request_json(base_url, "/v1/pair", method="POST", body=body)[0] == 401
    finally:
        server.shutdown()
        server.server_close()


def test_pairing_session_can_regenerate_after_use():
    pairing = PairingSession()
    original = pairing.code
    assert pairing.consume(original)
    assert pairing.snapshot()["used"] is True

    pairing.regenerate()

    assert pairing.snapshot()["used"] is False
    assert pairing.code != original
    assert pairing.consume(pairing.code)


def test_mobile_bridge_service_writes_lifecycle_status(tmp_path):
    status_path = tmp_path / "bridge-status.json"
    regenerate_path = tmp_path / "regenerate.request"
    service = MobileBridgeService(port=0, status_path=status_path, regenerate_path=regenerate_path)

    assert service.start()
    running = json.loads(status_path.read_text(encoding="utf-8"))
    assert running["running"] is True
    assert running["port"] > 0

    service.stop()
    stopped = json.loads(status_path.read_text(encoding="utf-8"))
    assert stopped["running"] is False
