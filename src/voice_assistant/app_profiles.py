from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .catalog import CATALOG_PATH
from .config import USER_CONFIG_ROOT
from .process_targets import normalize_process_name
from .storage import atomic_write_text


APP_PROFILES_PATH = USER_CONFIG_ROOT / "app_profiles.json"
CLOSE_BEHAVIORS = frozenset({"graceful_then_force", "graceful_only", "window_only"})
MAX_PROFILE_PROCESSES = 8
MAX_PROFILE_TITLES = 8


@dataclass(frozen=True)
class AppProfile:
    preferred_processes: list[str]
    window_titles: list[str]
    close_behavior: str = "graceful_then_force"


DEFAULT_PROFILE = AppProfile([], [], "graceful_then_force")


def _normalize_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def validate_profile(
    preferred_processes: list[str],
    window_titles: list[str],
    close_behavior: str,
) -> AppProfile:
    if close_behavior not in CLOSE_BEHAVIORS:
        raise ValueError("Invalid close behavior")
    if len(preferred_processes) > MAX_PROFILE_PROCESSES:
        raise ValueError(f"At most {MAX_PROFILE_PROCESSES} preferred processes are allowed")
    processes: list[str] = []
    for value in preferred_processes:
        normalized = normalize_process_name(value)
        if normalized is None:
            raise ValueError(f"Unsafe or invalid process name: {value}")
        if normalized not in processes:
            processes.append(normalized)
    titles = _normalize_values(window_titles)
    if len(titles) > MAX_PROFILE_TITLES:
        raise ValueError(f"At most {MAX_PROFILE_TITLES} window titles are allowed")
    if any(len(title) < 3 or len(title) > 120 for title in titles):
        raise ValueError("Window titles must contain between 3 and 120 characters")
    return AppProfile(processes, titles, close_behavior)


def load_profiles(path: Path = APP_PROFILES_PATH) -> dict[str, AppProfile]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    profiles: dict[str, AppProfile] = {}
    for app_name, value in raw.items():
        if not isinstance(app_name, str) or not isinstance(value, dict):
            continue
        try:
            profile = validate_profile(
                list(value.get("preferred_processes", [])),
                list(value.get("window_titles", [])),
                str(value.get("close_behavior", "graceful_then_force")),
            )
        except (TypeError, ValueError):
            continue
        profiles[app_name] = profile
    return profiles


def profile_for(app_name: str, path: Path = APP_PROFILES_PATH) -> AppProfile:
    return load_profiles(path).get(app_name, DEFAULT_PROFILE)


class AppProfileStore:
    def __init__(self, catalog_path: Path = CATALOG_PATH, path: Path = APP_PROFILES_PATH) -> None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.app_names = sorted({entry["name"] for entry in catalog}, key=str.casefold)
        self.path = path
        self.data = load_profiles(path)

    def get(self, app_name: str) -> AppProfile:
        return self.data.get(app_name, DEFAULT_PROFILE)

    def set(
        self,
        app_name: str,
        preferred_processes: list[str],
        window_titles: list[str],
        close_behavior: str,
    ) -> AppProfile:
        if app_name not in self.app_names:
            raise ValueError(f"Unknown catalog app: {app_name}")
        profile = validate_profile(preferred_processes, window_titles, close_behavior)
        if profile == DEFAULT_PROFILE:
            self.data.pop(app_name, None)
        else:
            self.data[app_name] = profile
        return profile

    def save(self) -> None:
        serialized = {
            app_name: asdict(self.data[app_name])
            for app_name in sorted(self.data, key=str.casefold)
        }
        atomic_write_text(
            self.path,
            json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        )
