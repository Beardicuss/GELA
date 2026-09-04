from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import platform
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlparse

from .config import USER_DATA_ROOT
from .private_network import private_network_status
from .remote_commands import RemoteCommandResult, execute_text_command
from .runtime_status import read_runtime_status
from .screen_sharing import (
    ScreenSharingStatus,
    capture_screen_jpeg,
    grant_screen_sharing,
    is_private_proxy_source,
    revoke_screen_sharing,
    screen_sharing_status,
)
from .storage import atomic_write_text, replace_file


PROTOCOL_VERSION = 1
DEFAULT_PORT = 8765
DEFAULT_DISCOVERY_PORT = 8766
PAIRING_TTL_SECONDS = 300
MAX_BODY_BYTES = 512 * 1024
MAX_AUDIO_BYTES = 1_500_000
MAX_CLIPBOARD_CHARACTERS = 100_000
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_OUTBOX_FILES = 100
MAX_SECURITY_AUDIT_EVENTS = 200
TOKEN_ROTATION_GRACE_SECONDS = 300
DEVICES_PATH = USER_DATA_ROOT / "mobile" / "paired_devices.json"
SECURITY_AUDIT_PATH = USER_DATA_ROOT / "mobile" / "security_audit.json"
BRIDGE_STATUS_PATH = USER_DATA_ROOT / "mobile" / "bridge_status.json"
REGENERATE_REQUEST_PATH = USER_DATA_ROOT / "mobile" / "regenerate_pairing_code.request"
BRIDGE_ID_PATH = USER_DATA_ROOT / "mobile" / "bridge_id.txt"
MOBILE_TRANSFER_ROOT = USER_DATA_ROOT / "mobile" / "transfers"
MOBILE_INBOX_PATH = MOBILE_TRANSFER_ROOT / "inbox"
MOBILE_OUTBOX_PATH = MOBILE_TRANSFER_ROOT / "outbox"
DISCOVERY_REQUEST = b"GELA_DISCOVER_V1"
MAC_ADDRESS_PATTERN = re.compile(r"(?i)(?:[0-9a-f]{2}[-:]){5}[0-9a-f]{2}")
INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DeviceStore:
    def __init__(self, path: Path = DEVICES_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def issue(self, device_name: str = "Gela Mobile") -> tuple[str, str]:
        device_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._lock:
            devices = self._load()
            devices[device_id] = {
                "name": device_name[:80],
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "created_at": now,
                "last_seen_at": now,
                "last_seen_epoch": time.time(),
            }
            atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
        return device_id, token

    def authenticate(self, token: str) -> str | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            devices = self._load()
            matched_id: str | None = None
            now_epoch = time.time()
            for device_id, item in devices.items():
                primary = str(item.get("token_hash", ""))
                previous = str(item.get("previous_token_hash", ""))
                try:
                    previous_expires = float(item.get("previous_token_expires_at", 0))
                except (TypeError, ValueError):
                    previous_expires = 0
                if secrets.compare_digest(primary, digest) or (
                    previous_expires > now_epoch and secrets.compare_digest(previous, digest)
                ):
                    matched_id = device_id
                    try:
                        last_seen_epoch = float(item.get("last_seen_epoch", 0))
                    except (TypeError, ValueError):
                        last_seen_epoch = 0
                    if now_epoch - last_seen_epoch >= 60:
                        item["last_seen_epoch"] = now_epoch
                        item["last_seen_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
                        atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
            return matched_id

    def list_public(self, current_device_id: str) -> list[dict[str, object]]:
        with self._lock:
            devices = self._load()
        return [
            {
                "deviceId": device_id,
                "name": str(item.get("name", "Gela Mobile"))[:80],
                "createdAt": item.get("created_at"),
                "lastSeenAt": item.get("last_seen_at"),
                "rotatedAt": item.get("rotated_at"),
                "current": device_id == current_device_id,
            }
            for device_id, item in devices.items()
        ]

    def any_recently_seen(self, maximum_age_seconds: float = 90.0) -> bool:
        now = time.time()
        with self._lock:
            devices = self._load()
        for item in devices.values():
            try:
                if now - float(item.get("last_seen_epoch", 0)) <= maximum_age_seconds:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            devices = self._load()
            if device_id not in devices:
                return False
            del devices[device_id]
            atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
        return True

    def rotate(self, device_id: str) -> str | None:
        token = secrets.token_urlsafe(32)
        with self._lock:
            devices = self._load()
            item = devices.get(device_id)
            if item is None:
                return None
            item["previous_token_hash"] = item.get("token_hash", "")
            item["previous_token_expires_at"] = time.time() + TOKEN_ROTATION_GRACE_SECONDS
            item["token_hash"] = hashlib.sha256(token.encode("utf-8")).hexdigest()
            item["rotated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
        return token

    def confirm_rotation(self, device_id: str, token: str) -> bool:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            devices = self._load()
            item = devices.get(device_id)
            if item is None or not secrets.compare_digest(str(item.get("token_hash", "")), digest):
                return False
            item.pop("previous_token_hash", None)
            item.pop("previous_token_expires_at", None)
            atomic_write_text(self.path, json.dumps(devices, ensure_ascii=False, indent=2) + "\n")
        return True

    def discovery_proofs(self, device_id: str, nonce: str, client_address: str) -> list[str]:
        with self._lock:
            item = self._load().get(device_id)
        if item is None:
            return []
        token_hashes = [str(item.get("token_hash", ""))]
        try:
            previous_expires = float(item.get("previous_token_expires_at", 0))
        except (TypeError, ValueError):
            previous_expires = 0
        if previous_expires > time.time():
            token_hashes.append(str(item.get("previous_token_hash", "")))
        return [
            hashlib.sha256(f"{nonce}:{token_hash}:{client_address}".encode("utf-8")).hexdigest()
            for token_hash in token_hashes
            if len(token_hash) == 64
        ]


class SecurityAuditStore:
    def __init__(self, path: Path = SECURITY_AUDIT_PATH, maximum_events: int = MAX_SECURITY_AUDIT_EVENTS) -> None:
        self.path = path
        self.maximum_events = maximum_events
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, object]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def append(self, event_type: str, actor_device_id: str, target_device_id: str | None = None) -> None:
        event = {
            "id": secrets.token_hex(8),
            "type": event_type[:50],
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "actorDeviceId": actor_device_id,
            "targetDeviceId": target_device_id,
        }
        with self._lock:
            events = self._load()
            events.append(event)
            atomic_write_text(
                self.path,
                json.dumps(events[-self.maximum_events :], ensure_ascii=False, indent=2) + "\n",
            )

    def list_recent(self) -> list[dict[str, object]]:
        with self._lock:
            return list(reversed(self._load()[-self.maximum_events :]))


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


def load_bridge_id(path: Path = BRIDGE_ID_PATH) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
        if len(value) == 32 and all(character in "0123456789abcdef" for character in value):
            return value
    except OSError:
        pass
    value = secrets.token_hex(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, value + "\n")
    return value


def wake_mac_addresses() -> list[str]:
    """Return adapter MAC addresses that a paired phone can target with Wake-on-LAN."""
    if platform.system() != "Windows":
        return []
    try:
        result = subprocess.run(
            ["getmac.exe", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted({match.group(0).replace("-", ":").upper() for match in MAC_ADDRESS_PATTERN.finditer(result.stdout)})


def ensure_transfer_directories(root: Path = MOBILE_TRANSFER_ROOT) -> tuple[Path, Path]:
    inbox = root / "inbox"
    outbox = root / "outbox"
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    return inbox, outbox


def safe_transfer_filename(value: str) -> str:
    decoded = unquote(value).strip()
    cleaned = INVALID_FILENAME_CHARACTERS.sub("_", Path(decoded).name).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        return "mobile-file"
    return cleaned[:180]


def available_transfer_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    for index in range(1, 10_000):
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not allocate a transfer filename")


def read_windows_clipboard() -> str:
    if platform.system() != "Windows":
        raise RuntimeError("Clipboard exchange is available only on Windows")
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); Get-Clipboard -Raw -Format Text",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Could not read the Windows clipboard") from exc
    return result.stdout[:MAX_CLIPBOARD_CHARACTERS]


def write_windows_clipboard(text: str) -> None:
    if platform.system() != "Windows":
        raise RuntimeError("Clipboard exchange is available only on Windows")
    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); Set-Clipboard -Value ([Console]::In.ReadToEnd())",
            ],
            check=True,
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Could not update the Windows clipboard") from exc


def create_handler(
    pairing: PairingSession,
    devices: DeviceStore,
    executor: Callable[[str, str], RemoteCommandResult] = execute_text_command,
    audio_recognizer: Callable[[bytes, int, int], object] | None = None,
    bridge_id: str = "",
    clipboard_reader: Callable[[], str] = read_windows_clipboard,
    clipboard_writer: Callable[[str], None] = write_windows_clipboard,
    transfer_root: Path = MOBILE_TRANSFER_ROOT,
    audit_store: SecurityAuditStore | None = None,
    screen_capture: Callable[[int, int, int, bool], tuple[bytes, int, int]] = capture_screen_jpeg,
    screen_status: Callable[[], ScreenSharingStatus] = screen_sharing_status,
    screen_grant: Callable[[], ScreenSharingStatus] = grant_screen_sharing,
    screen_revoke: Callable[[], ScreenSharingStatus] = revoke_screen_sharing,
    command_observer: Callable[[RemoteCommandResult], None] = lambda _result: None,
) -> type[BaseHTTPRequestHandler]:
    limiter = AttemptLimiter()
    discovery_limiter = AttemptLimiter(limit=30)
    screen_limiter = AttemptLimiter(limit=180)
    screen_permission_limiter = AttemptLimiter(limit=10)
    audit = audit_store or SecurityAuditStore(devices.path.with_name("security_audit.json"))
    transfer_lock = threading.Lock()
    inbox_path, outbox_path = ensure_transfer_directories(transfer_root)

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

        def _binary(self, path: Path) -> None:
            size = path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(path.name, safe='')}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with path.open("rb") as source:
                while chunk := source.read(64 * 1024):
                    self.wfile.write(chunk)

        def _jpeg(self, content: bytes, width: int, height: int) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Gela-Screen-Width", str(width))
            self.send_header("X-Gela-Screen-Height", str(height))
            self.end_headers()
            self.wfile.write(content)

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

        def _raw_body(self, maximum_size: int) -> bytes | None:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if size <= 0 or size > maximum_size:
                return None
            return self.rfile.read(size)

        def _authenticated_device(self) -> str | None:
            header = self.headers.get("Authorization", "")
            return devices.authenticate(header[7:]) if header.startswith("Bearer ") else None

        def _authorized(self) -> bool:
            return self._authenticated_device() is not None

        def do_GET(self) -> None:  # noqa: N802
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            if path == "/v1/info":
                self._json(HTTPStatus.OK, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "service": "gela-pc-bridge",
                    "computerName": platform.node() or "Windows PC",
                    "bridgeId": bridge_id,
                    "pairingRequired": True,
                })
                return
            if path == "/v1/discovery/verify":
                client_address = self.client_address[0]
                if not discovery_limiter.allow(client_address):
                    self._json(HTTPStatus.TOO_MANY_REQUESTS, {"message": "Too many discovery verification attempts."})
                    return
                query = parse_qs(parsed_url.query, keep_blank_values=True)
                device_id = query.get("deviceId", [""])[0]
                nonce = query.get("nonce", [""])[0]
                if not re.fullmatch(r"[0-9a-f]{32}", device_id) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid discovery verification request."})
                    return
                proofs = devices.discovery_proofs(device_id, nonce, client_address)
                if not proofs:
                    self._json(HTTPStatus.NOT_FOUND, {"message": "Paired device not found."})
                    return
                self._json(HTTPStatus.OK, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "bridgeId": bridge_id,
                    "clientAddress": client_address,
                    "proofs": proofs,
                })
                return
            if path == "/v1/status":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                private_network = private_network_status()
                self._json(HTTPStatus.OK, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "gela": read_runtime_status(),
                    "bridgeId": bridge_id,
                    "wakeMacAddresses": wake_mac_addresses(),
                    "remoteBaseUrl": private_network.remote_base_url,
                    "screenSharing": screen_status().to_dict(),
                })
                return
            if path == "/v1/screen/frame":
                device_id = self._authenticated_device()
                if device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if not is_private_proxy_source(self.client_address[0]):
                    self._json(HTTPStatus.UPGRADE_REQUIRED, {
                        "message": "Screen viewing requires Gela's private HTTPS address.",
                    })
                    return
                permission = screen_status()
                if not permission.authorized:
                    self._json(HTTPStatus.FORBIDDEN, {
                        "message": "Screen sharing is not authorized on the PC.",
                    })
                    return
                if not screen_limiter.allow(device_id):
                    self._json(HTTPStatus.TOO_MANY_REQUESTS, {"message": "Screen frame rate is limited."})
                    return
                query = parse_qs(parsed_url.query, keep_blank_values=True)
                try:
                    width = int(query.get("width", ["960"])[0])
                    height = int(query.get("height", ["540"])[0])
                    quality = int(query.get("quality", ["58"])[0])
                    all_screens = query.get("screens", ["primary"])[0] == "all"
                    content, frame_width, frame_height = screen_capture(width, height, quality, all_screens)
                except (OSError, RuntimeError, ValueError) as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                        "message": f"Screen capture failed: {str(exc)[:160]}",
                    })
                    return
                self._jpeg(content, frame_width, frame_height)
                return
            if path == "/v1/devices":
                current_device_id = self._authenticated_device()
                if current_device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                self._json(HTTPStatus.OK, {
                    "devices": devices.list_public(current_device_id),
                    "currentDeviceId": current_device_id,
                })
                return
            if path == "/v1/security/audit":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                self._json(HTTPStatus.OK, {"events": audit.list_recent()})
                return
            if path == "/v1/clipboard":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                try:
                    text = clipboard_reader()
                except RuntimeError as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(exc)})
                    return
                self._json(HTTPStatus.OK, {"text": text[:MAX_CLIPBOARD_CHARACTERS]})
                return
            if path == "/v1/files/outbox":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                files = []
                for item in sorted(outbox_path.iterdir(), key=lambda candidate: candidate.stat().st_mtime, reverse=True):
                    if not item.is_file() or item.stat().st_size > MAX_FILE_BYTES:
                        continue
                    stat = item.stat()
                    files.append({
                        "id": quote(item.name, safe=""),
                        "name": item.name,
                        "size": stat.st_size,
                        "modifiedAt": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    })
                    if len(files) >= MAX_OUTBOX_FILES:
                        break
                self._json(HTTPStatus.OK, {"files": files, "maximumFileBytes": MAX_FILE_BYTES})
                return
            if path.startswith("/v1/files/outbox/"):
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                requested_name = unquote(path.removeprefix("/v1/files/outbox/"))
                if not requested_name or requested_name != Path(requested_name).name:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid transfer filename."})
                    return
                candidate = outbox_path / requested_name
                if not candidate.is_file() or candidate.stat().st_size > MAX_FILE_BYTES:
                    self._json(HTTPStatus.NOT_FOUND, {"message": "Transfer file not found or exceeds the size limit."})
                    return
                self._binary(candidate)
                return
            self._json(HTTPStatus.NOT_FOUND, {"message": "Endpoint not found."})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/v1/recognition/audio":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if audio_recognizer is None:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"message": "PC audio recognition is unavailable."})
                    return
                try:
                    protocol_version = int(self.headers.get("X-Gela-Protocol-Version", "0"))
                    sample_rate = int(self.headers.get("X-Gela-Sample-Rate", "0"))
                    channels = int(self.headers.get("X-Gela-Channels", "0"))
                except ValueError:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid audio metadata."})
                    return
                request_id = self.headers.get("X-Gela-Request-Id", "")[:100]
                audio = self._raw_body(MAX_AUDIO_BYTES)
                if (
                    protocol_version != PROTOCOL_VERSION
                    or not request_id
                    or audio is None
                    or len(audio) < 1_600
                    or sample_rate < 8_000
                    or sample_rate > 48_000
                    or channels not in {1, 2}
                ):
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid or unsupported PCM audio request."})
                    return
                try:
                    recognized = audio_recognizer(audio, sample_rate, channels)
                except TimeoutError as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(exc)})
                    return
                except Exception:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "PC speech recognition failed."})
                    return
                transcript = str(getattr(recognized, "text", ""))[:500]
                confidence = float(getattr(recognized, "confidence", 0.0))
                self._json(HTTPStatus.OK, {
                    "requestId": request_id,
                    "transcript": transcript,
                    "confidence": confidence,
                    "alternatives": [],
                })
                return
            if path == "/v1/files/inbox":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if self.headers.get("X-Gela-Protocol-Version") != str(PROTOCOL_VERSION):
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid transfer protocol version."})
                    return
                content = self._raw_body(MAX_FILE_BYTES)
                if content is None:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "File is empty or exceeds the 25 MB limit."})
                    return
                filename = safe_transfer_filename(self.headers.get("X-Gela-Filename", "mobile-file"))
                try:
                    with transfer_lock:
                        destination = available_transfer_path(inbox_path, filename)
                        temporary = destination.with_name(destination.name + ".uploading")
                        temporary.write_bytes(content)
                        replace_file(temporary, destination)
                except OSError:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Could not store the transferred file."})
                    return
                self._json(HTTPStatus.CREATED, {
                    "name": destination.name,
                    "size": len(content),
                    "message": "File saved to the protected Gela mobile inbox.",
                })
                return
            body = self._body()
            if body is None:
                self._json(HTTPStatus.BAD_REQUEST, {"message": "A valid JSON request is required."})
                return
            if path == "/v1/screen/permission":
                current_device_id = self._authenticated_device()
                if current_device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if not is_private_proxy_source(self.client_address[0]):
                    self._json(HTTPStatus.UPGRADE_REQUIRED, {
                        "message": "Remote screen authorization requires Gela's private HTTPS address.",
                    })
                    return
                if not screen_permission_limiter.allow(current_device_id):
                    self._json(HTTPStatus.TOO_MANY_REQUESTS, {"message": "Too many screen authorization requests."})
                    return
                if body.get("protocolVersion") != PROTOCOL_VERSION or body.get("action") not in {"grant", "revoke"}:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid screen authorization request."})
                    return
                action = str(body["action"])
                permission = screen_grant() if action == "grant" else screen_revoke()
                audit.append(
                    "screen-permission-granted" if action == "grant" else "screen-permission-revoked",
                    current_device_id,
                    current_device_id,
                )
                self._json(HTTPStatus.OK, {"screenSharing": permission.to_dict()})
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
                audit.append("device-paired", device_id, device_id)
                private_network = private_network_status()
                self._json(HTTPStatus.CREATED, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "computerName": platform.node() or "Windows PC",
                    "deviceId": device_id,
                    "accessToken": token,
                    "bridgeId": bridge_id,
                    "wakeMacAddresses": wake_mac_addresses(),
                    "remoteBaseUrl": private_network.remote_base_url,
                })
                return
            if path == "/v1/token/rotate":
                current_device_id = self._authenticated_device()
                if current_device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if body.get("protocolVersion") != PROTOCOL_VERSION:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid protocol version."})
                    return
                token = devices.rotate(current_device_id)
                if token is None:
                    self._json(HTTPStatus.NOT_FOUND, {"message": "Paired device not found."})
                    return
                audit.append("token-rotated", current_device_id, current_device_id)
                self._json(HTTPStatus.OK, {
                    "deviceId": current_device_id,
                    "accessToken": token,
                    "confirmationWindowSeconds": TOKEN_ROTATION_GRACE_SECONDS,
                })
                return
            if path == "/v1/token/confirm":
                current_device_id = self._authenticated_device()
                header = self.headers.get("Authorization", "")
                token = header[7:] if header.startswith("Bearer ") else ""
                if current_device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if body.get("protocolVersion") != PROTOCOL_VERSION or not devices.confirm_rotation(current_device_id, token):
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "The new access token is required."})
                    return
                audit.append("token-confirmed", current_device_id, current_device_id)
                self._json(HTTPStatus.OK, {"message": "New access token confirmed."})
                return
            revoke_match = re.fullmatch(r"/v1/devices/([0-9a-f]{32})/revoke", path)
            if revoke_match:
                current_device_id = self._authenticated_device()
                if current_device_id is None:
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                if body.get("protocolVersion") != PROTOCOL_VERSION:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid protocol version."})
                    return
                target_device_id = revoke_match.group(1)
                if not devices.revoke(target_device_id):
                    self._json(HTTPStatus.NOT_FOUND, {"message": "Paired device not found."})
                    return
                audit.append("device-revoked", current_device_id, target_device_id)
                self._json(HTTPStatus.OK, {
                    "message": "Paired device revoked.",
                    "revokedDeviceId": target_device_id,
                    "revokedCurrentDevice": target_device_id == current_device_id,
                })
                return
            if path == "/v1/clipboard":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                    return
                text = body.get("text")
                if body.get("protocolVersion") != PROTOCOL_VERSION or not isinstance(text, str) or len(text) > MAX_CLIPBOARD_CHARACTERS:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Clipboard text is invalid or exceeds the limit."})
                    return
                try:
                    clipboard_writer(text)
                except RuntimeError as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(exc)})
                    return
                self._json(HTTPStatus.OK, {"message": "Windows clipboard updated.", "characters": len(text)})
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
                command_observer(result)
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
        audio_recognizer: Callable[[bytes, int, int], object] | None = None,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        bridge_id_path: Path = BRIDGE_ID_PATH,
        command_observer: Callable[[RemoteCommandResult], None] = lambda _result: None,
    ) -> None:
        self.host = host
        self.port = port
        self.status_path = status_path
        self.regenerate_path = regenerate_path
        self.audio_recognizer = audio_recognizer
        self.command_observer = command_observer
        self.discovery_port = discovery_port
        self.bridge_id = load_bridge_id(bridge_id_path)
        self.pairing = PairingSession()
        self.devices = DeviceStore()
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        self.discovery_thread: threading.Thread | None = None
        self.discovery_socket: socket.socket | None = None
        self.stop_event = threading.Event()
        self.error: str | None = None

    @property
    def running(self) -> bool:
        return self.server_thread is not None and self.server_thread.is_alive()

    def _status_payload(self) -> dict[str, object]:
        pairing = self.pairing.snapshot()
        private_network = private_network_status()
        screen = screen_sharing_status()
        port = self.server.server_address[1] if self.server is not None else self.port
        return {
            "running": self.running,
            "error": self.error,
            "port": port,
            "addresses": [f"{address}:{port}" for address in local_ipv4_addresses()],
            "bridge_id": self.bridge_id,
            "discovery_port": self.discovery_port,
            "private_network": private_network.to_dict(),
            "screen_sharing": screen.to_dict(),
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

    def _discover(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.discovery_port))
            self.discovery_port = sock.getsockname()[1]
            sock.settimeout(0.5)
            while not self.stop_event.is_set():
                try:
                    payload, address = sock.recvfrom(256)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if payload != DISCOVERY_REQUEST:
                    continue
                port = self.server.server_address[1] if self.server is not None else self.port
                response = json.dumps({
                    "protocolVersion": PROTOCOL_VERSION,
                    "service": "gela-pc-bridge",
                    "bridgeId": self.bridge_id,
                    "computerName": platform.node() or "Windows PC",
                    "port": port,
                }).encode("utf-8")
                try:
                    sock.sendto(response, address)
                except OSError:
                    continue
        finally:
            sock.close()
            self.discovery_socket = None

    def start(self) -> bool:
        if self.running:
            return True
        self.stop_event.clear()
        self.error = None
        try:
            self.server = ThreadingHTTPServer(
                (self.host, self.port),
                create_handler(
                    self.pairing,
                    self.devices,
                    audio_recognizer=self.audio_recognizer,
                    bridge_id=self.bridge_id,
                    command_observer=self.command_observer,
                ),
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
        self.discovery_thread = threading.Thread(
            target=self._discover,
            name="gela-mobile-discovery",
            daemon=True,
        )
        self.discovery_thread.start()
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
        if self.discovery_socket is not None:
            self.discovery_socket.close()
        if self.server_thread is not None:
            self.server_thread.join(timeout=3)
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=2)
        if self.discovery_thread is not None:
            self.discovery_thread.join(timeout=2)
        self.server = None
        self.discovery_thread = None
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
