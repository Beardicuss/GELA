from __future__ import annotations

from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import platform
import secrets
import threading
from typing import Callable

from .config import USER_DATA_ROOT
from .remote_commands import RemoteCommandResult, execute_text_command
from .storage import atomic_write_text


MCU_PORT = 8767
MCU_PROTOCOL_VERSION = 2
MCU_TOKEN_PATH = USER_DATA_ROOT / "mcu" / "board_token.txt"
MAX_MCU_AUDIO_BYTES = 180_000
MCU_CAPABILITIES = (
    "face-state-v1",
    "push-audio-pcm8k-v1",
    "cancel-v1",
    "toggle-mute-v1",
    "status-v2",
    "pc-health-v1",
)
MCU_EVENT_TYPES = frozenset({"boot", "wifi-connected", "pc-reconnected", "command-started", "command-finished", "action"})
def load_mcu_token(path: Path = MCU_TOKEN_PATH) -> str:
    try:
        token = path.read_text(encoding="ascii").strip()
        if len(token) >= 32:
            return token
    except OSError:
        pass
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, token + "\n")
    return token


def create_mcu_handler(
    token: str,
    *,
    audio_recognizer: Callable[[bytes, int, int], object],
    executor: Callable[[str, str], RemoteCommandResult] = execute_text_command,
    status_supplier: Callable[[], dict[str, object]],
    cancel: Callable[[], None],
    toggle_mute: Callable[[], None],
    command_observer: Callable[[RemoteCommandResult], None] = lambda _result: None,
    connection_observer: Callable[[str], None] = lambda _address: None,
) -> type[BaseHTTPRequestHandler]:
    class McuHandler(BaseHTTPRequestHandler):
        server_version = "GelaMCU/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            supplied = header[7:] if header.startswith("Bearer ") else ""
            return bool(supplied) and secrets.compare_digest(supplied, token)

        def _json(self, status: int, payload: dict[str, object]) -> None:
            encoded = json.dumps(payload, ensure_ascii=True).encode("ascii")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self, maximum: int) -> bytes | None:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            return self.rfile.read(size) if 0 < size <= maximum else None

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/mcu/status":
                self._json(HTTPStatus.NOT_FOUND, {"message": "Endpoint not found."})
                return
            if not self._authorized():
                logging.warning("Rejected unauthenticated MCU request from %s", self.client_address[0])
                self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                return
            connection_observer(self.client_address[0])
            payload = dict(status_supplier())
            payload.update(
                protocolVersion=MCU_PROTOCOL_VERSION,
                minimumProtocolVersion=1,
                capabilities=list(MCU_CAPABILITIES),
                computerName=platform.node() or "Windows PC",
            )
            self._json(HTTPStatus.OK, payload)

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                logging.warning("Rejected unauthenticated MCU request from %s", self.client_address[0])
                self._json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."})
                return
            connection_observer(self.client_address[0])
            if self.path == "/v1/mcu/audio":
                try:
                    declared_size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    declared_size = 0
                if declared_size > MAX_MCU_AUDIO_BYTES:
                    self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"message": "PCM audio is too large."})
                    return
                audio = self._body(MAX_MCU_AUDIO_BYTES)
                if audio is None or len(audio) < 1_600:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Invalid PCM audio."})
                    return
                try:
                    recognized = audio_recognizer(audio, 8_000, 1)
                    transcript = str(getattr(recognized, "text", ""))[:500]
                    logging.info(
                        "MCU command transcription: %s (confidence=%.3f)",
                        transcript or "[nothing]",
                        float(getattr(recognized, "confidence", 0.0)),
                    )
                    result = executor(transcript, "ka")
                    command_observer(result)
                except TimeoutError as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(exc)})
                    return
                except Exception:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Board command failed."})
                    return
                payload = asdict(result)
                payload["matchedCommand"] = payload.pop("matched_command")
                payload["confidence"] = float(getattr(recognized, "confidence", 0.0))
                self._json(HTTPStatus.OK, payload)
                return
            if self.path == "/v1/mcu/action":
                raw = self._body(256)
                try:
                    action = json.loads(raw.decode("ascii"))["action"] if raw else ""
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
                    action = ""
                callback = {"cancel": cancel, "toggle-mute": toggle_mute}.get(action)
                if callback is None:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Unsupported board action."})
                    return
                callback()
                self._json(HTTPStatus.OK, {"status": "executed", "action": action})
                return
            if self.path == "/v1/mcu/event":
                raw = self._body(512)
                try:
                    event = json.loads(raw.decode("ascii")) if raw else {}
                    event_type = event["type"]
                    detail = str(event.get("detail", ""))[:120]
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
                    event_type, detail = "", ""
                if event_type not in MCU_EVENT_TYPES:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Unsupported board event."})
                    return
                logging.info("MCU event from %s: %s%s", self.client_address[0], event_type, f" ({detail})" if detail else "")
                self._json(HTTPStatus.OK, {"status": "accepted"})
                return
            self._json(HTTPStatus.NOT_FOUND, {"message": "Endpoint not found."})

    return McuHandler


class McuTerminalService:
    def __init__(self, **handler_options: object) -> None:
        self.handler_options = handler_options
        self.token = load_mcu_token()
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self._last_client_address: str | None = None

    def _observe_connection(self, address: str) -> None:
        if address != self._last_client_address:
            logging.info("Gela MCU Wi-Fi connected from %s", address)
            self._last_client_address = address

    def start(self) -> bool:
        if self.thread is not None and self.thread.is_alive():
            return True
        try:
            self.server = ThreadingHTTPServer(
                ("0.0.0.0", MCU_PORT),
                create_mcu_handler(
                    self.token,
                    connection_observer=self._observe_connection,
                    **self.handler_options,
                ),
            )
        except OSError as exc:
            self.error = str(exc)
            return False
        self.thread = threading.Thread(target=self.server.serve_forever, name="gela-mcu-wifi", daemon=True)
        self.thread.start()
        self.error = None
        logging.info("Gela MCU Wi-Fi bridge listening on port %d (protocol %d)", MCU_PORT, MCU_PROTOCOL_VERSION)
        return True

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)
        self.server = None
        self.thread = None
        self._last_client_address = None
