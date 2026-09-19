from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .config import USER_DATA_ROOT
from .storage import atomic_write_text


NOTES_RUNTIME_ROOT = USER_DATA_ROOT / "runtime" / "notes"
DRAFT_PATH = NOTES_RUNTIME_ROOT / "draft.txt"
STATE_PATH = NOTES_RUNTIME_ROOT / "state.json"
DICTATION_STOP_PHRASES = ("გელა შეწყვიტე წერა", "gela stop writing")
PUNCTUATION_PHRASES = {
    "კითხვის ნიშანი": "?",
    "ძახილის ნიშანი": "!",
    "მრავალ წერტილი": "...",
    "მრავალწერტილი": "...",
    "ორი წერილი": ":",
    "ახალი ხაზი": "\n",
    "წერტილი": ".",
    "მძიმე": ",",
    "question mark": "?",
    "new line": "\n",
    "period": ".",
    "comma": ",",
}


def desktop_path() -> Path:
    """Return the user's configured Windows Desktop, including redirected desktops."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _kind = winreg.QueryValueEx(key, "Desktop")
            return Path(os.path.expandvars(str(value))).expanduser()
        except OSError:
            pass
    return Path.home() / "Desktop"


def read_state() -> dict[str, object]:
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": False, "revision": 0, "status": "ready"}
    return raw if isinstance(raw, dict) else {"active": False, "revision": 0, "status": "ready"}


def write_state(*, active: bool, status: str, language: str | None = None) -> None:
    previous = read_state()
    payload = {
        "active": active,
        "revision": int(previous.get("revision", 0)) + 1,
        "status": status,
    }
    if language:
        payload["language"] = language
    elif previous.get("language"):
        payload["language"] = previous["language"]
    atomic_write_text(STATE_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def prepare_blank_note() -> None:
    atomic_write_text(DRAFT_PATH, "")
    write_state(active=False, status="ready")


def ensure_draft() -> None:
    if not DRAFT_PATH.is_file():
        atomic_write_text(DRAFT_PATH, "")


def append_transcript(text: str) -> None:
    cleaned = "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()
    if not cleaned:
        return
    ensure_draft()
    existing = DRAFT_PATH.read_text(encoding="utf-8")
    separator = "" if not existing or existing[-1].isspace() else " "
    atomic_write_text(DRAFT_PATH, f"{existing}{separator}{cleaned}")


def split_stop_phrase(transcript: str) -> tuple[str, bool]:
    normalized = " ".join(transcript.casefold().split())
    for phrase in DICTATION_STOP_PHRASES:
        if normalized == phrase:
            return "", True
        marker = f" {phrase}"
        if normalized.endswith(marker):
            return normalized[: -len(marker)].strip(), True
    return normalized, False


def format_dictation_text(transcript: str) -> str:
    result = transcript
    for phrase in sorted(PUNCTUATION_PHRASES, key=len, reverse=True):
        result = re.sub(
            rf"(?<!\S){re.escape(phrase)}(?!\S)",
            PUNCTUATION_PHRASES[phrase],
            result,
            flags=re.IGNORECASE,
        )
    result = re.sub(r"[ \t]+(\.\.\.|[.,?!:])", r"\1", result)
    result = re.sub(r"[ \t]*\n[ \t]*", "\n", result)
    return result.strip()


def detected_language(text: str) -> str:
    has_georgian = any("\u10A0" <= character <= "\u10FF" for character in text)
    has_latin = any("a" <= character.casefold() <= "z" for character in text)
    if has_georgian and has_latin:
        return "ქართული + English"
    if has_georgian:
        return "ქართული"
    if has_latin:
        return "English"
    return "ავტომატური"


def save_final_note() -> Path:
    ensure_draft()
    destination = desktop_path() / "gela.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        backup = destination.with_name(f"gela_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")
        backup.write_bytes(destination.read_bytes())
    atomic_write_text(destination, DRAFT_PATH.read_text(encoding="utf-8"))
    return destination


def launch_notes_window() -> None:
    command = (
        [sys.executable, "--notes-window"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "voice_assistant.notes_window"]
    )
    subprocess.Popen(command, close_fds=True)


def open_blank_note() -> str:
    prepare_blank_note()
    launch_notes_window()
    return "notes ready"


def request_dictation_start() -> str:
    ensure_draft()
    write_state(active=True, status="listening")
    launch_notes_window()
    return "notes writing"


def request_dictation_stop(*, save: bool = False) -> str:
    write_state(active=False, status="stopped")
    if save:
        return f"notes stopped saved={save_final_note()}"
    return "notes stopped"
