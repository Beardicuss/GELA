from __future__ import annotations

import logging
import queue
import threading
import time

import serial
from serial.tools import list_ports


BOARD_VID = 0x303A
BOARD_PID = 0x1001
ALLOWED_STATES = frozenset({"IDLE", "LISTEN", "THINK", "ERROR", "SUCCESS", "TALK"})

STATUS_STATES = {
    "listening_command": "LISTEN",
    "listening_question": "LISTEN",
    "listening_online_query": "LISTEN",
    "executing": "THINK",
    "answering_question": "THINK",
    "fetching_online": "THINK",
    "recognizing_mobile": "THINK",
    "error": "ERROR",
    "recovering_audio": "ERROR",
}

SUCCESS_EVENTS = frozenset({"launch_success", "already_running", "already_stopped", "already_on", "already_off"})
ERROR_EVENTS = frozenset({"launch_failed", "command_not_understood", "microphone_error"})


def state_for_status(status: str) -> str:
    return STATUS_STATES.get(status, "IDLE")


def state_for_response(event: str) -> str:
    if event in SUCCESS_EVENTS:
        return "SUCCESS"
    if event in ERROR_EVENTS:
        return "ERROR"
    if event == "ready":
        return "LISTEN"
    if event == "cancelled":
        return "IDLE"
    return "TALK"


def find_board_port() -> str | None:
    matches = [port.device for port in list_ports.comports() if port.vid == BOARD_VID and port.pid == BOARD_PID]
    return sorted(matches)[0] if matches else None


class McuFaceBridge:
    """Reconnectable, non-blocking USB state sender for the Gela face board."""

    def __init__(self, retry_seconds: float = 2.0) -> None:
        self.retry_seconds = retry_seconds
        self._states: queue.Queue[str] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._desired_state = "IDLE"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gela-mcu-face", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._offer("IDLE")
        if self._thread is not None:
            self._thread.join(timeout=2)

    def show(self, state: str) -> None:
        state = state.upper()
        if state not in ALLOWED_STATES:
            raise ValueError("Unsupported MCU face state")
        self._desired_state = state
        self._offer(state)

    def on_status(self, status: str) -> None:
        self.show(state_for_status(status))

    def on_response(self, event: str, active: bool, current_status: str) -> None:
        self.show(state_for_response(event) if active else state_for_status(current_status))

    @property
    def desired_state(self) -> str:
        return self._desired_state

    def _offer(self, state: str) -> None:
        try:
            self._states.get_nowait()
        except queue.Empty:
            pass
        try:
            self._states.put_nowait(state)
        except queue.Full:
            pass

    def _run(self) -> None:
        connection: serial.Serial | None = None
        connected_port: str | None = None
        while not self._stop.is_set():
            try:
                if connection is None:
                    port = find_board_port()
                    if port is None:
                        self._stop.wait(self.retry_seconds)
                        continue
                    connection = serial.Serial(port, 115200, timeout=0.1, write_timeout=0.5)
                    connection.reset_input_buffer()
                    connected_port = port
                    logging.info("Gela MCU face connected on %s", port)
                    connection.write(("GELA1 STATE " + self._desired_state + "\n").encode("ascii"))
                    connection.flush()
                try:
                    state = self._states.get(timeout=0.5)
                except queue.Empty:
                    continue
                connection.write(("GELA1 STATE " + state + "\n").encode("ascii"))
                connection.flush()
            except (OSError, serial.SerialException):
                if connected_port is not None:
                    logging.info("Gela MCU face disconnected from %s", connected_port)
                if connection is not None:
                    try:
                        connection.close()
                    except OSError:
                        pass
                connection = None
                connected_port = None
                self._stop.wait(self.retry_seconds)
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
