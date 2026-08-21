from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import platform
from pathlib import Path
import secrets
import socket
import threading
import time
from typing import Callable
from urllib.parse import urlparse

from .config import USER_DATA_ROOT
from .remote_commands import RemoteCommandResult, execute_text_command
from .runtime_status import read_runtime_status
from .storage import atomic_write_text


PROTOCOL_VERSION = 1
DEFAULT_PORT = 8765
PAIRING_TTL_SECONDS = 300
MAX_BODY_BYTES = 64 * 1024
DEVICES_PATH = USER_DATA_ROOT / "mobile" / "paired_devices.json"
BRIDGE_STATUS_PATH = USER_DATA_ROOT / "mobile" / "bridge_status.json"
REGENERATE_REQUEST_PATH = USER_DATA_ROOT / "mobile" / "regenerate_pairing_code.request"


class DeviceStore:
    def __init__(self, path: Path = DEVICES_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def issue(self, device_name: str = "Gela Mobile") -> tuple[str, str]:
        device_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        with self._lock:
            devices = self._load()
            devices[device_id] = {
                "name": device_name[:80],
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            }
            atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
        return device_id, token

    def authenticate(self, token: str) -> bool:
        if not token:
            return False
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            devices = self._load()
        return any(secrets.compare_digest(item.get("token_hash", ""), digest) for item in devices.values())


class PairingSession:
    def __init__(self, ttl_seconds: int = PAIRING_TTL_SECONDS) -> None:
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.expires_at = time.monotonic() + ttl_seconds
        self._used = False
        self._lock = threading.Lock()

    def consume(self, candidate: str) -> bool:
        with self._lock:
            valid = not self._used and time.monotonic() < self.expires_at
            if not valid or not secrets.compare_digest(self.code, candidate):
                return False
            self._used = True
            return True

    def regenerate(self, ttl_seconds: int = PAIRING_TTL_SECONDS) -> None:
        with self._lock:
            self.code = f"{secrets.randbelow(1_000_000):06d}"
            self.expires_at = time.monotonic() + ttl_seconds
            self._used = False

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            remaining = max(0, int(self.expires_at - time.monotonic()))
            return {"pairing_code": self.code, "remaining_seconds": remaining, "used": self._used}


class AttemptLimiter:
    def __init__(self, limit: int = 8, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, address: str) -> bool:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[address]
            while attempts and attempts[0] <= now - self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.limit:
                return False
            attempts.append(now)
            return True


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = item[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def create_handler(
    pairing: PairingSession,
    devices: DeviceStore,
    executor: Callable[[str, str], RemoteCommandResult] = execute_text_command,
) -> type[BaseHTTPRequestHandler]:
    limiter = AttemptLimiter()

    class BridgeHandler(BaseHTTPRequestHandler):
        server_version = "GelaBridge/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _json(self, status: int, payload: dict[str, object]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self) -> dict[str, object] | None:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if size <= 0 or size > MAX_BODY_BYTES:
                return None
            try:
                value = json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            return value if isinstance(value, dict) else None

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            return header.startswith("Bearer ") and devices.authenticate(header[7:])

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/v1/info":
                self._json(HTTPStatus.OK, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "service": "gela-pc-bridge",
                    "computerName": platform.node() or "Windows PC",
                    "pairingRequired": True,
                })
                return
            if path == "/v1/status":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                self._json(HTTPStatus.OK, {"protocolVersion": PROTOCOL_VERSION, "gela": read_runtime_status()})
                return
            self._json(HTTPStatus.NOT_FOUND, {"message": "Endpoint not found."})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            body = self._body()
            if body is None:
                self._json(HTTPStatus.BAD_REQUEST, {"message": "A valid JSON request is required."})
                return
            if path == "/v1/pair":
                address = self.client_address[0]
                if not limiter.allow(address):
                    self._json(HTTPStatus.TOO_MANY_REQUESTS, {"message": "Too many pairing attempts."})
                    return
                if body.get("protocolVersion") != PROTOCOL_VERSION or not pairing.consume(str(body.get("pairingCode", ""))):
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "The pairing code is invalid or expired."})
                    return
                device_id, token = devices.issue(str(body.get("deviceName", "Gela Mobile")))
                self._json(HTTPStatus.CREATED, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "computerName": platform.node() or "Windows PC",
                    "deviceId": device_id,
                    "accessToken": token,
                })
                return
            if path == "/v1/commands/text":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                transcript = str(body.get("transcript", ""))[:500]
                language = str(body.get("language", "ka"))
                request_id = str(body.get("requestId", ""))[:100]
                if body.get("protocolVersion") != PROTOCOL_VERSION or language not in {"ka", "en"} or not request_id or not transcript.strip():
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid command request."})
                    return
                result = executor(transcript, language)
                payload = asdict(result)
                payload["requestId"] = request_id
                payload["matchedCommand"] = payload.pop("matched_command")
                self._json(HTTPStatus.OK, payload)
                return
            self._json(HTTPStatus.NOT_FOUND, {"message": "Endpoint not found."})

    return BridgeHandler


class MobileBridgeService:
    """Own the mobile HTTP server for the lifetime of the desktop tray app."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        status_path: Path = BRIDGE_STATUS_PATH,
        regenerate_path: Path = REGENERATE_REQUEST_PATH,
    ) -> None:
        self.host = host
        self.port = port
        self.status_path = status_path
        self.regenerate_path = regenerate_path
        self.pairing = PairingSession()
        self.devices = DeviceStore()
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.error: str | None = None

    @property
    def running(self) -> bool:
        return self.server_thread is not None and self.server_thread.is_alive()

    def _status_payload(self) -> dict[str, object]:
        pairing = self.pairing.snapshot()
        port = self.server.server_address[1] if self.server is not None else self.port
        return {
            "running": self.running,
            "error": self.error,
            "port": port,
            "addresses": [f"{address}:{port}" for address in local_ipv4_addresses()],
            **pairing,
        }

    def _write_status(self) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.status_path,
            json.dumps(self._status_payload(), ensure_ascii=False, indent=2) + "\n",
        )

    def _monitor(self) -> None:
        while not self.stop_event.wait(1):
            if self.regenerate_path.exists():
                try:
                    self.regenerate_path.unlink()
                except OSError:
                    pass
                self.pairing.regenerate()
            self._write_status()

    def start(self) -> bool:
        if self.running:
            return True
        self.stop_event.clear()
        self.error = None
        try:
            self.server = ThreadingHTTPServer(
                (self.host, self.port),
                create_handler(self.pairing, self.devices),
            )
        except OSError as exc:
            self.error = str(exc)
            self._write_status()
            return False
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            name="gela-mobile-bridge",
            daemon=True,
        )
        self.server_thread.start()
        self.monitor_thread = threading.Thread(
            target=self._monitor,
            name="gela-mobile-bridge-status",
            daemon=True,
        )
        self.monitor_thread.start()
        self._write_status()
        return True

    def stop(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread is not None:
            self.server_thread.join(timeout=3)
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=2)
        self.server = None
        self.error = None
        self._write_status()


def serve_mobile_bridge(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    pairing = PairingSession()
    addresses = local_ipv4_addresses() or ["127.0.0.1"]
    print("Gela mobile bridge is ready.")
    print(f"Pairing code: {pairing.code} (expires in {PAIRING_TTL_SECONDS // 60} minutes)")
    for address in addresses:
        print(f"PC address: {address}:{port}")
    print("Press Ctrl+C to stop.")
    server = ThreadingHTTPServer((host, port), create_handler(pairing, DeviceStore()))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
