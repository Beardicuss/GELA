from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .storage import atomic_write_text


@dataclass(frozen=True)
class AliasSyncReport:
    archived: dict[str, list[str]]
    restored: dict[str, list[str]]


def _normalize(value: str) -> str:
    value = value.casefold().replace("™", " ").replace("®", " ")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _load_aliases(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Alias file must contain an object: {path}")
    return {
        str(app_name): [str(alias) for alias in aliases]
        for app_name, aliases in raw.items()
        if isinstance(aliases, list)
    }


def _merge_aliases(existing: list[str], incoming: list[str]) -> list[str]:
    result = list(existing)
    known = {_normalize(alias) for alias in result}
    for alias in incoming:
        normalized = _normalize(alias)
        if normalized and normalized not in known:
            result.append(alias)
            known.add(normalized)
    return result


def synchronize_alias_files(
    app_names: list[str] | set[str],
    georgian_path: Path,
    english_path: Path,
    archive_path: Path,
) -> AliasSyncReport:
    """Archive aliases for absent apps and restore them if the app returns."""
    current_apps = set(app_names)
    paths = {"ka": georgian_path, "en": english_path}
    active = {language: _load_aliases(path) for language, path in paths.items()}
    if archive_path.is_file():
        raw_archive = json.loads(archive_path.read_text(encoding="utf-8"))
        if not isinstance(raw_archive, dict):
            raise ValueError(f"Alias archive must contain an object: {archive_path}")
    else:
        raw_archive = {}
    archive = {
        language: {
            str(app_name): [str(alias) for alias in aliases]
            for app_name, aliases in raw_archive.get(language, {}).items()
            if isinstance(aliases, list)
        }
        for language in paths
    }
    archived = {language: [] for language in paths}
    restored = {language: [] for language in paths}

    for language in paths:
        data = active[language]
        saved = archive[language]
        for app_name in sorted(set(data) - current_apps, key=str.casefold):
            saved[app_name] = _merge_aliases(saved.get(app_name, []), data.pop(app_name))
            archived[language].append(app_name)

        owners = {
            _normalize(alias): app_name
            for app_name, aliases in data.items()
            for alias in aliases
            if _normalize(alias)
        }
        for app_name in sorted(set(saved) & current_apps, key=str.casefold):
            current = data.get(app_name, [])
            restored_values: list[str] = []
            remaining: list[str] = []
            for alias in saved[app_name]:
                normalized = _normalize(alias)
                owner = owners.get(normalized)
                if normalized and owner not in (None, app_name):
                    remaining.append(alias)
                    continue
                current = _merge_aliases(current, [alias])
                owners[normalized] = app_name
                restored_values.append(alias)
            if restored_values:
                data[app_name] = current
                restored[language].append(app_name)
            if remaining:
                saved[app_name] = remaining
            else:
                saved.pop(app_name, None)

    for language, path in paths.items():
        serialized = json.dumps(active[language], ensure_ascii=False, indent=2) + "\n"
        if not path.is_file() or path.read_text(encoding="utf-8") != serialized:
            atomic_write_text(path, serialized)
    serialized_archive = json.dumps(archive, ensure_ascii=False, indent=2) + "\n"
    if not archive_path.is_file() or archive_path.read_text(encoding="utf-8") != serialized_archive:
        atomic_write_text(archive_path, serialized_archive)
    return AliasSyncReport(archived, restored)
