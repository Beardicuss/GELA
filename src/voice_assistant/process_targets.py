from __future__ import annotations

import json
import logging
from pathlib import Path, PureWindowsPath
import re
import threading

from .config import PROJECT_ROOT, USER_CONFIG_ROOT
from .storage import atomic_write_text


DEFAULT_PROCESS_TARGETS_PATH = PROJECT_ROOT / "config" / "process_targets.json"
LEARNED_PROCESS_TARGETS_PATH = USER_CONFIG_ROOT / "learned_process_targets.json"
MAX_LEARNED_PROCESSES_PER_APP = 8
_PROCESS_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
_UNSAFE_PROCESS_NAMES = frozenset(
    {
        "applicationframehost",
        "cmd",
        "conhost",
        "dllhost",
        "dwm",
        "explorer",
        "openwith",
        "powershell",
        "pwsh",
        "rundll32",
        "searchhost",
        "shellexperiencehost",
        "startmenuexperiencehost",
        "svchost",
        "taskhostw",
    }
)
_WRITE_LOCK = threading.Lock()


def normalize_process_name(value: str) -> str | None:
    name = PureWindowsPath(str(value).strip()).name
    if name.casefold().endswith(".exe"):
        name = name[:-4]
    name = name.casefold().strip()
    if not _PROCESS_NAME_PATTERN.fullmatch(name) or name in _UNSAFE_PROCESS_NAMES:
        return None
    return name


def _read_targets(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logging.warning("Ignoring unreadable process-target file: %s", path)
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for app_name, values in raw.items():
        if not isinstance(app_name, str) or not isinstance(values, list):
            continue
        names = [name for value in values if (name := normalize_process_name(str(value)))]
        if names:
            result[app_name] = list(dict.fromkeys(names))
    return result


def load_process_targets(
    default_path: Path = DEFAULT_PROCESS_TARGETS_PATH,
    learned_path: Path = LEARNED_PROCESS_TARGETS_PATH,
) -> dict[str, list[str]]:
    merged = _read_targets(default_path)
    for app_name, names in _read_targets(learned_path).items():
        current = merged.setdefault(app_name, [])
        current.extend(name for name in names if name not in current)
    return merged


def process_targets_for(
    app_name: str,
    default_path: Path = DEFAULT_PROCESS_TARGETS_PATH,
    learned_path: Path = LEARNED_PROCESS_TARGETS_PATH,
) -> list[str]:
    return load_process_targets(default_path, learned_path).get(app_name, [])


def learned_process_targets_for(
    app_name: str,
    learned_path: Path = LEARNED_PROCESS_TARGETS_PATH,
) -> list[str]:
    return _read_targets(learned_path).get(app_name, [])


def remember_process_target(
    app_name: str,
    process_name: str,
    default_path: Path = DEFAULT_PROCESS_TARGETS_PATH,
    learned_path: Path = LEARNED_PROCESS_TARGETS_PATH,
) -> bool:
    """Persist one verified process without modifying factory mappings."""
    app_name = app_name.strip()
    normalized = normalize_process_name(process_name)
    if not app_name or normalized is None:
        return False
    with _WRITE_LOCK:
        if normalized in load_process_targets(default_path, learned_path).get(app_name, []):
            return False
        learned = _read_targets(learned_path)
        current = learned.setdefault(app_name, [])
        if len(current) >= MAX_LEARNED_PROCESSES_PER_APP:
            logging.warning("Process learning limit reached for %s", app_name)
            return False
        current.append(normalized)
        serialized = json.dumps(
            {key: learned[key] for key in sorted(learned, key=str.casefold)},
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        atomic_write_text(learned_path, serialized)
    return True
