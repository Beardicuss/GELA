from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

from .config import PROJECT_ROOT, USER_DATA_ROOT
from .single_instance import SingleInstanceLock
from .storage import atomic_write_text
from .windows_process import hidden_process_kwargs


RUNTIME_ROOT = USER_DATA_ROOT / "runtime" / "supervisor"
INTENTIONAL_EXIT_PATH = RUNTIME_ROOT / "intentional_exit"
STATUS_PATH = RUNTIME_ROOT / "status.json"
LOG_PATH = USER_DATA_ROOT / "logs" / "supervisor.log"
SUPERVISOR_MUTEX = "Local\\GelaVoiceAssistantSupervisor"


def mark_intentional_exit() -> None:
    """Tell the supervisor that the tray Exit command was deliberate."""
    if os.environ.get("GELA_SUPERVISED") != "1":
        return
    atomic_write_text(INTENTIONAL_EXIT_PATH, datetime.now(timezone.utc).isoformat())


def _child_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--supervised-child"]
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe") if sys.platform == "win32" else executable
    return [str(pythonw), "-m", "voice_assistant.tray", "--supervised-child"]


def _write_status(**values: object) -> None:
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), **values}
    atomic_write_text(STATUS_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )


def run_supervisor() -> int:
    """Keep the tray process alive, with bounded backoff after repeated crashes."""
    lock = SingleInstanceLock(SUPERVISOR_MUTEX)
    if not lock.acquire():
        return 0
    _configure_logging()
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    recent_failures: deque[float] = deque()
    recovery_count = 0
    recovered = False
    try:
        while True:
            INTENTIONAL_EXIT_PATH.unlink(missing_ok=True)
            environment = os.environ.copy()
            environment["GELA_SUPERVISED"] = "1"
            if not recovered:
                environment["GELA_AUTO_OPEN_HOME"] = "1"
            if recovered:
                environment["GELA_RECOVERED"] = "1"
            started = time.monotonic()
            _write_status(state="running", recovery_count=recovery_count)
            try:
                child = subprocess.Popen(
                    _child_command(),
                    cwd=Path(sys.executable).parent if getattr(sys, "frozen", False) else PROJECT_ROOT,
                    env=environment,
                    close_fds=True,
                    **hidden_process_kwargs(),
                )
                exit_code = child.wait()
            except Exception:
                logging.exception("Could not launch supervised Gela process")
                exit_code = -1

            if INTENTIONAL_EXIT_PATH.exists():
                INTENTIONAL_EXIT_PATH.unlink(missing_ok=True)
                _write_status(state="stopped_by_user", exit_code=exit_code, recovery_count=recovery_count)
                logging.info("Gela stopped from its tray menu")
                return 0

            runtime = time.monotonic() - started
            now = time.monotonic()
            recent_failures.append(now)
            while recent_failures and now - recent_failures[0] > 600:
                recent_failures.popleft()
            recovery_count += 1
            recovered = True
            delay = 2 if runtime >= 60 else min(60, 2 ** min(len(recent_failures), 6))
            _write_status(
                state="recovering",
                exit_code=exit_code,
                runtime_seconds=round(runtime, 1),
                restart_delay_seconds=delay,
                recovery_count=recovery_count,
            )
            logging.warning(
                "Gela exited unexpectedly with code %s after %.1fs; restarting in %ss",
                exit_code,
                runtime,
                delay,
            )
            time.sleep(delay)
    finally:
        lock.close()
