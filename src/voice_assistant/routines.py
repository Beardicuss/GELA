from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time

from .catalog import CATALOG_PATH, CatalogEntry, load_catalog, normalize_phrase
from .config import USER_CONFIG_ROOT
from .launcher import launch_verified
from .storage import atomic_write_text


ROUTINES_PATH = USER_CONFIG_ROOT / "routines.json"
MAX_ROUTINE_APPS = 10


@dataclass(frozen=True)
class Routine:
    name: str
    aliases: dict[str, list[str]]
    apps: list[str]


def load_routines(
    path: Path = ROUTINES_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> list[Routine]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    routines = [Routine(**item) for item in raw.get("routines", [])]
    validate_routines(routines, catalog_path)
    return routines


def validate_routines(routines: list[Routine], catalog_path: Path = CATALOG_PATH) -> None:
    entries = load_catalog(catalog_path)
    app_names = {entry.name for entry in entries}
    from .actions import build_action_phrases
    from .intent import expand_intent_phrases
    from .recognizer import command_phrases

    english_path = USER_CONFIG_ROOT / "english_aliases.json"
    english_aliases = json.loads(english_path.read_text(encoding="utf-8")) if english_path.is_file() else {}
    ka_commands = command_phrases(entries, "ka")
    ka_commands.update(build_action_phrases(entries, "ka", english_aliases))
    entries_by_name = {entry.name: entry for entry in entries}
    en_commands = {
        normalize_phrase(alias): entries_by_name[name]
        for name, values in english_aliases.items()
        if name in entries_by_name
        for alias in values
    }
    en_commands.update(build_action_phrases(entries, "en", english_aliases))
    reserved = {
        "ka": set(expand_intent_phrases(ka_commands, "ka")),
        "en": set(expand_intent_phrases(en_commands, "en")),
    }
    routine_names: set[str] = set()
    aliases: dict[tuple[str, str], str] = {}
    for routine in routines:
        name = routine.name.strip()
        if not name:
            raise ValueError("Routine name cannot be empty")
        normalized_name = normalize_phrase(name)
        if normalized_name in routine_names:
            raise ValueError(f"Duplicate routine name: {name}")
        routine_names.add(normalized_name)
        if not 1 <= len(routine.apps) <= MAX_ROUTINE_APPS:
            raise ValueError(f"Routine {name!r} must contain 1–{MAX_ROUTINE_APPS} applications")
        missing = [app for app in routine.apps if app not in app_names]
        if missing:
            raise ValueError(f"Routine {name!r} references missing apps: {', '.join(missing)}")
        if not any(routine.aliases.get(language) for language in ("ka", "en")):
            raise ValueError(f"Routine {name!r} needs at least one voice alias")
        for language in ("ka", "en"):
            for alias in routine.aliases.get(language, []):
                normalized = normalize_phrase(alias)
                if not normalized:
                    raise ValueError(f"Routine {name!r} contains an empty alias")
                if normalized in reserved[language]:
                    raise ValueError(f"Routine alias {alias!r} conflicts with an existing command")
                key = language, normalized
                owner = aliases.get(key)
                if owner is not None and owner != name:
                    raise ValueError(f"Routine alias {alias!r} is already used by {owner}")
                aliases[key] = name


def save_routines(
    routines: list[Routine],
    path: Path = ROUTINES_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> None:
    validate_routines(routines, catalog_path)
    ordered = sorted(routines, key=lambda routine: routine.name.casefold())
    atomic_write_text(
        path,
        json.dumps({"routines": [asdict(routine) for routine in ordered]}, ensure_ascii=False, indent=2)
        + "\n",
    )


def routine_phrases(
    language: str,
    path: Path = ROUTINES_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> dict[str, Routine]:
    return {
        normalize_phrase(alias): routine
        for routine in load_routines(path, catalog_path)
        for alias in routine.aliases.get(language, [])
    }


def execute_routine(routine: Routine, entries: list[CatalogEntry] | None = None) -> str:
    entries = entries or load_catalog()
    by_name = {entry.name: entry for entry in entries}
    launched: list[str] = []
    for index, app_name in enumerate(routine.apps):
        entry = by_name.get(app_name)
        if entry is None:
            raise RuntimeError(f"Routine application is no longer available: {app_name}")
        launch_verified(entry)
        launched.append(app_name)
        if index < len(routine.apps) - 1:
            time.sleep(0.5)
    return ", ".join(launched)
