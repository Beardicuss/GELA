from __future__ import annotations

from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from voice_assistant.mobile_bridge import (
    DISCOVERY_REQUEST,
    DeviceStore,
    MobileBridgeService,
    PairingSession,
    create_handler,
    load_bridge_id,
    wake_mac_addresses,
)
from voice_assistant.remote_commands import RemoteCommandResult
from voice_assistant.recognizer import RecognitionResult
from voice_assistant.screen_sharing import ScreenSharingStatus


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


def request_audio(base_url: str, audio: bytes, token: str, request_id: str = "audio-1"):
    request = Request(
        base_url + "/v1/recognition/audio",
        data=audio,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "X-Gela-Protocol-Version": "1",
            "X-Gela-Request-Id": request_id,
            "X-Gela-Sample-Rate": "16000",
            "X-Gela-Channels": "1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def start_server(tmp_path: Path, **handler_options):
    pairing = PairingSession(ttl_seconds=60)
    devices = DeviceStore(tmp_path / "devices.json")
    executed = []

    def executor(transcript: str, language: str):
        executed.append((transcript, language))
        return RemoteCommandResult("executed", transcript, "Test command", "Done")

    handler_options.setdefault("transfer_root", tmp_path / "transfers")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(pairing, devices, executor, bridge_id="test-bridge", **handler_options),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, pairing, devices, executed, f"http://127.0.0.1:{server.server_port}"


def test_paired_device_management_rotation_and_audit(tmp_path):
    server, pairing, devices, _, base_url = start_server(tmp_path)
    try:
        _, first = request_json(
            base_url,
            "/v1/pair",
            method="POST",
            body={"protocolVersion": 1, "pairingCode": pairing.code, "deviceName": "DanTe phone"},
        )
        second_id, second_token = devices.issue("Tablet")

        status, listing = request_json(base_url, "/v1/devices", token=first["accessToken"])
        assert status == 200
        assert listing["currentDeviceId"] == first["deviceId"]
        assert {item["deviceId"] for item in listing["devices"]} == {first["deviceId"], second_id}
        assert all("token_hash" not in item and "accessToken" not in item for item in listing["devices"])

        nonce = "1" * 32
        status, verification = request_json(
            base_url,
            f"/v1/discovery/verify?deviceId={first['deviceId']}&nonce={nonce}",
        )
        token_hash = hashlib.sha256(first["accessToken"].encode("utf-8")).hexdigest()
        expected_proof = hashlib.sha256(f"{nonce}:{token_hash}:127.0.0.1".encode("utf-8")).hexdigest()
        assert status == 200
        assert verification["bridgeId"] == "test-bridge"
        assert verification["clientAddress"] == "127.0.0.1"
        assert expected_proof in verification["proofs"]
        assert first["accessToken"] not in json.dumps(verification)

        status, rotated = request_json(
            base_url,
            "/v1/token/rotate",
            method="POST",
            token=first["accessToken"],
            body={"protocolVersion": 1},
        )
        assert status == 200
        new_token = rotated["accessToken"]
        assert new_token != first["accessToken"]
        assert devices.authenticate(first["accessToken"]) == first["deviceId"]
        assert devices.authenticate(new_token) == first["deviceId"]

        status, _ = request_json(
            base_url,
            "/v1/token/confirm",
            method="POST",
            token=new_token,
            body={"protocolVersion": 1},
        )
        assert status == 200
        assert devices.authenticate(first["accessToken"]) is None

        status, revoked = request_json(
            base_url,
            f"/v1/devices/{second_id}/revoke",
            method="POST",
            token=new_token,
            body={"protocolVersion": 1},
        )
        assert status == 200
        assert revoked["revokedCurrentDevice"] is False
        assert devices.authenticate(second_token) is None

        status, audit = request_json(base_url, "/v1/security/audit", token=new_token)
        assert status == 200
        assert [event["type"] for event in audit["events"]][:3] == [
            "device-revoked",
            "token-confirmed",
            "token-rotated",
        ]
        assert "accessToken" not in json.dumps(audit)
        assert "token_hash" not in json.dumps(audit)
    finally:
        server.shutdown()
        server.server_close()


def test_device_management_requires_authentication_and_valid_device_id(tmp_path):
    server, _, devices, _, base_url = start_server(tmp_path)
    token = devices.issue()[1]
    try:
        assert request_json(base_url, "/v1/devices")[0] == 401
        assert request_json(base_url, "/v1/security/audit")[0] == 401
        status, _ = request_json(
            base_url,
            "/v1/devices/not-a-device/revoke",
            method="POST",
            token=token,
            body={"protocolVersion": 1},
        )
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()


def request_bytes(base_url: str, path: str, *, method: str = "GET", data=None, token=None, headers=None):
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = Request(base_url + path, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def test_pair_then_execute_authenticated_command(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "voice_assistant.mobile_bridge.read_runtime_status",
        lambda: {"status": "sleeping", "microphone_state": "ready", "updated_at": "2026-08-22T15:00:00+04:00"},
    )
    server, pairing, devices, executed, base_url = start_server(tmp_path)
    try:
        status, info = request_json(base_url, "/v1/info")
        assert status == 200
        assert info["service"] == "gela-pc-bridge"
        assert info["bridgeId"] == "test-bridge"

        status, paired = request_json(
            base_url,
            "/v1/pair",
            method="POST",
            body={"protocolVersion": 1, "pairingCode": pairing.code},
        )
        assert status == 201
        assert devices.authenticate(paired["accessToken"])
        assert paired["bridgeId"] == "test-bridge"
        assert "wakeMacAddresses" in paired

        status, live = request_json(base_url, "/v1/status", token=paired["accessToken"])
        assert status == 200
        assert live["gela"]["status"] == "sleeping"
        assert live["gela"]["microphone_state"] == "ready"

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


def test_screen_frame_requires_auth_and_pc_permission(tmp_path):
    permission = ScreenSharingStatus(authorized=False)

    def status():
        return permission

    def capture(width: int, height: int, quality: int, all_screens: bool):
        assert (width, height, quality, all_screens) == (800, 450, 55, False)
        return b"\xff\xd8test-jpeg\xff\xd9", 800, 450

    server, _, devices, _, base_url = start_server(
        tmp_path,
        screen_capture=capture,
        screen_status=status,
    )
    token = devices.issue()[1]
    try:
        assert request_bytes(base_url, "/v1/screen/frame")[0] == 401
        assert request_bytes(base_url, "/v1/screen/frame", token=token)[0] == 403
        permission = ScreenSharingStatus(authorized=True, remaining_seconds=600)
        code, content, headers = request_bytes(
            base_url,
            "/v1/screen/frame?width=800&height=450&quality=55",
            token=token,
        )
        assert code == 200
        assert content.startswith(b"\xff\xd8")
        assert headers["Content-Type"] == "image/jpeg"
        assert headers["X-Gela-Screen-Width"] == "800"
        assert headers["Cache-Control"].startswith("no-store")
    finally:
        server.shutdown()
        server.server_close()


def test_paired_phone_can_grant_and_revoke_screen_permission_over_private_proxy(tmp_path):
    permission = ScreenSharingStatus(authorized=False)

    def grant():
        nonlocal permission
        permission = ScreenSharingStatus(authorized=True, remaining_seconds=900)
        return permission

    def revoke():
        nonlocal permission
        permission = ScreenSharingStatus(authorized=False)
        return permission

    server, _, devices, _, base_url = start_server(
        tmp_path,
        screen_status=lambda: permission,
        screen_grant=grant,
        screen_revoke=revoke,
    )
    token = devices.issue()[1]
    request = {"protocolVersion": 1, "action": "grant"}
    try:
        assert request_json(base_url, "/v1/screen/permission", method="POST", body=request)[0] == 401
        code, result = request_json(
            base_url,
            "/v1/screen/permission",
            method="POST",
            body=request,
            token=token,
        )
        assert code == 200
        assert result["screenSharing"]["authorized"] is True
        assert result["screenSharing"]["remaining_seconds"] == 900
        assert result["screenSharing"]["remote_only"] is True
        code, result = request_json(
            base_url,
            "/v1/screen/permission",
            method="POST",
            body={"protocolVersion": 1, "action": "revoke"},
            token=token,
        )
        assert code == 200
        assert result["screenSharing"]["authorized"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_authenticated_audio_is_transcribed_without_executing(tmp_path):
    pairing = PairingSession(ttl_seconds=60)
    devices = DeviceStore(tmp_path / "devices.json")
    token = devices.issue()[1]
    recognized_audio = []

    def recognize(audio: bytes, sample_rate: int, channels: int):
        recognized_audio.append((audio, sample_rate, channels))
        return RecognitionResult("გახსენი სთიმი", 1.0)

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(pairing, devices, audio_recognizer=recognize),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, result = request_audio(
            f"http://127.0.0.1:{server.server_port}",
            b"\x00\x00" * 800,
            token,
        )
        assert status == 200
        assert result["transcript"] == "გახსენი სთიმი"
        assert result["confidence"] == 1.0
        assert result["alternatives"] == []
        assert recognized_audio == [(b"\x00\x00" * 800, 16000, 1)]
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


def test_authenticated_clipboard_exchange_is_bounded(tmp_path):
    clipboard = ["PC clipboard"]
    server, _, devices, _, base_url = start_server(
        tmp_path,
        clipboard_reader=lambda: clipboard[0],
        clipboard_writer=lambda text: clipboard.__setitem__(0, text),
    )
    token = devices.issue()[1]
    try:
        status, response = request_json(base_url, "/v1/clipboard", token=token)
        assert status == 200
        assert response["text"] == "PC clipboard"

        status, response = request_json(
            base_url,
            "/v1/clipboard",
            method="POST",
            token=token,
            body={"protocolVersion": 1, "text": "ტელეფონის ტექსტი"},
        )
        assert status == 200
        assert response["characters"] == len("ტელეფონის ტექსტი")
        assert clipboard[0] == "ტელეფონის ტექსტი"

        assert request_json(base_url, "/v1/clipboard")[0] == 401
    finally:
        server.shutdown()
        server.server_close()


def test_authenticated_file_transfer_stays_inside_inbox_and_outbox(tmp_path):
    transfer_root = tmp_path / "transfers"
    server, _, devices, _, base_url = start_server(tmp_path, transfer_root=transfer_root)
    token = devices.issue()[1]
    content = b"bounded mobile file"
    headers = {
        "Content-Type": "application/octet-stream",
        "X-Gela-Protocol-Version": "1",
        "X-Gela-Filename": quote("../notes.txt", safe=""),
    }
    try:
        status, payload, _ = request_bytes(
            base_url,
            "/v1/files/inbox",
            method="POST",
            data=content,
            token=token,
            headers=headers,
        )
        assert status == 201
        saved = json.loads(payload)
        assert saved["name"] == "notes.txt"
        assert (transfer_root / "inbox" / "notes.txt").read_bytes() == content
        assert not (tmp_path / "notes.txt").exists()

        outbox = transfer_root / "outbox"
        outgoing = outbox / "ანგარიში.txt"
        outgoing.write_bytes(b"pc outbound")
        status, listing = request_json(base_url, "/v1/files/outbox", token=token)
        assert status == 200
        assert listing["files"][0]["name"] == outgoing.name

        download_id = listing["files"][0]["id"]
        status, downloaded, response_headers = request_bytes(
            base_url,
            f"/v1/files/outbox/{download_id}",
            token=token,
        )
        assert status == 200
        assert downloaded == b"pc outbound"
        assert "attachment" in response_headers["Content-Disposition"]
        assert request_bytes(base_url, f"/v1/files/outbox/{download_id}")[0] == 401
    finally:
        server.shutdown()
        server.server_close()


def test_file_upload_rejects_content_over_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("voice_assistant.mobile_bridge.MAX_FILE_BYTES", 4)
    transfer_root = tmp_path / "limited-transfers"
    server, _, devices, _, base_url = start_server(tmp_path, transfer_root=transfer_root)
    token = devices.issue()[1]
    try:
        status, _, _ = request_bytes(
            base_url,
            "/v1/files/inbox",
            method="POST",
            data=b"12345",
            token=token,
            headers={
                "X-Gela-Protocol-Version": "1",
                "X-Gela-Filename": "oversized.txt",
            },
        )
        assert status == 400
        assert list((transfer_root / "inbox").iterdir()) == []
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


def test_wake_mac_addresses_normalizes_and_deduplicates(monkeypatch):
    monkeypatch.setattr("voice_assistant.mobile_bridge.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "voice_assistant.mobile_bridge.subprocess.run",
        lambda *args, **kwargs: type(
            "Result", (), {"stdout": '"Ethernet","AA-BB-CC-DD-EE-FF"\n"Wi-Fi","aa:bb:cc:dd:ee:ff"\n'}
        )(),
    )

    assert wake_mac_addresses() == ["AA:BB:CC:DD:EE:FF"]


def test_mobile_bridge_service_writes_lifecycle_status(tmp_path):
    status_path = tmp_path / "bridge-status.json"
    regenerate_path = tmp_path / "regenerate.request"
    service = MobileBridgeService(
        port=0,
        discovery_port=0,
        status_path=status_path,
        regenerate_path=regenerate_path,
        bridge_id_path=tmp_path / "bridge-id.txt",
    )

    assert service.start()
    running = json.loads(status_path.read_text(encoding="utf-8"))
    assert running["running"] is True
    assert running["port"] > 0

    service.stop()
    stopped = json.loads(status_path.read_text(encoding="utf-8"))
    assert stopped["running"] is False


def test_bridge_identity_is_stable_and_replaces_invalid_value(tmp_path):
    path = tmp_path / "bridge-id.txt"
    first = load_bridge_id(path)
    assert len(first) == 32
    assert load_bridge_id(path) == first

    path.write_text("not-valid\n", encoding="ascii")
    replacement = load_bridge_id(path)
    assert replacement != first
    assert len(replacement) == 32


def test_udp_discovery_returns_stable_bridge_identity(tmp_path):
    service = MobileBridgeService(
        host="127.0.0.1",
        port=0,
        discovery_port=0,
        status_path=tmp_path / "status.json",
        regenerate_path=tmp_path / "regenerate.request",
        bridge_id_path=tmp_path / "bridge-id.txt",
    )
    assert service.start()
    try:
        deadline = time.monotonic() + 2
        while service.discovery_port == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert service.discovery_port > 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(DISCOVERY_REQUEST, ("127.0.0.1", service.discovery_port))
            response = json.loads(client.recvfrom(2048)[0])
        assert response["service"] == "gela-pc-bridge"
        assert response["bridgeId"] == service.bridge_id
        assert response["port"] == service.server.server_port
    finally:
        service.stop()
