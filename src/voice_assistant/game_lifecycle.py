from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import threading

from .config import USER_DATA_ROOT
from .process_targets import normalize_process_name
from .storage import atomic_write_text


GAME_LIFECYCLE_PATH = USER_DATA_ROOT / "runtime" / "game_lifecycle.json"
LAUNCHER_PROCESS_NAMES = frozenset(
    {
        "epicgameslauncher",
        "epicwebhelper",
        "gameoverlayui",
        "steam",
        "steamservice",
        "steamwebhelper",
        "ubisoftconnect",
        "upc",
    }
)
ANTI_CHEAT_EXACT_NAMES = frozenset(
    {
        "beservice",
        "eaclauncher",
        "start_protected_game",
        "vgc",
        "vgtray",
    }
)
ANTI_CHEAT_MARKERS = ("anticheat", "battleye", "easyanticheat", "equ8")
_LOCK = threading.Lock()


def is_launcher_process(name: str) -> bool:
    normalized = normalize_process_name(name)
    return normalized in LAUNCHER_PROCESS_NAMES if normalized else False


def is_anti_cheat_process(name: str) -> bool:
    normalized = normalize_process_name(name)
    if not normalized:
        return False
    return normalized in ANTI_CHEAT_EXACT_NAMES or any(
        marker in normalized for marker in ANTI_CHEAT_MARKERS
    )


def is_gameplay_process(name: str) -> bool:
    normalized = normalize_process_name(name)
    return bool(normalized) and not is_launcher_process(normalized) and not is_anti_cheat_process(normalized)


def _read(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logging.warning("Ignoring unreadable game lifecycle file: %s", path)
        return {}
    return raw if isinstance(raw, dict) else {}


def record_game_observation(
    app_name: str,
    app_id: str,
    current_processes: set[str],
    before_processes: set[str],
    expected_game_processes: set[str],
    state: str,
    *,
    verified_process: str | None = None,
    path: Path = GAME_LIFECYCLE_PATH,
) -> dict[str, object]:
    normalized_current = {
        normalized
        for value in current_processes
        if (normalized := normalize_process_name(value)) is not None
    }
    normalized_before = {
        normalized
        for value in before_processes
        if (normalized := normalize_process_name(value)) is not None
    }
    normalized_expected = {
        normalized
        for value in expected_game_processes
        if (normalized := normalize_process_name(value)) is not None
    }
    launchers = sorted(name for name in normalized_current if is_launcher_process(name))
    anti_cheat = sorted(
        name
        for name in normalized_current - normalized_before
        if is_anti_cheat_process(name)
    )
    gameplay = sorted(
        name
        for name in normalized_current & normalized_expected
        if is_gameplay_process(name)
    )
    verified = normalize_process_name(verified_process or "")
    if verified and verified in normalized_current and is_gameplay_process(verified):
        gameplay = sorted(set(gameplay) | {verified})

    record: dict[str, object] = {
        "app_id": app_id,
        "state": state,
        "launcher_processes": launchers,
        "anti_cheat_processes": anti_cheat,
        "game_processes": gameplay,
    }
    with _LOCK:
        records = _read(path)
        previous = records.get(app_name, {})
        # Short-lived anti-cheat helpers can disappear before the real game
        # reaches stable verification, so retain those observed this session.
        previous_anti_cheat = previous.get("anti_cheat_processes", [])
        if state in {"launching", "running"} and isinstance(previous_anti_cheat, list):
            record["anti_cheat_processes"] = sorted(
                set(anti_cheat) | {str(name) for name in previous_anti_cheat}
            )
        if all(previous.get(key) == value for key, value in record.items()):
            return previous
        record["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        records[app_name] = record
        atomic_write_text(
            path,
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        )
    return record


def gameplay_processes_for(app_name: str, path: Path = GAME_LIFECYCLE_PATH) -> list[str]:
    record = _read(path).get(app_name, {})
    if record.get("state") not in {"launching", "running"}:
        return []
    values = record.get("game_processes", [])
    if not isinstance(values, list):
        return []
    return [name for value in values if (name := normalize_process_name(str(value)))]


def mark_game_stopped(app_name: str, path: Path = GAME_LIFECYCLE_PATH) -> None:
    with _LOCK:
        records = _read(path)
        previous = records.get(app_name)
        if not isinstance(previous, dict):
            return
        previous["state"] = "stopped"
        previous["game_processes"] = []
        previous["anti_cheat_processes"] = []
        previous["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        atomic_write_text(path, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
