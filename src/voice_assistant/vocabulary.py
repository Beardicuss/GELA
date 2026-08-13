from __future__ import annotations

import json
from pathlib import Path
import re

from vosk import Model, SetLogLevel

from .catalog import ALIASES_PATH, CATALOG_PATH, load_catalog, normalize_phrase
from .config import USER_CONFIG_ROOT, load_settings
from .storage import atomic_write_text


AUDIT_PATH = USER_CONFIG_ROOT / "vocabulary_audit.json"
GEORGIAN_RE = re.compile(r"[\u10A0-\u10FF]")


def _words(values: list[str]) -> set[str]:
    return {
        word
        for value in values
        for word in normalize_phrase(value).split()
        if word and GEORGIAN_RE.search(word)
    }


def probe_missing_words(words: set[str], language: str) -> set[str]:
    if not words:
        return set()
    if language not in {"ka", "en"}:
        raise ValueError("Unsupported vocabulary language")
    settings = load_settings()
    model_path = settings.models.get(language)
    if model_path is None:
        raise ValueError("Unsupported vocabulary language")
    SetLogLevel(-1)
    model = Model(str(model_path))
    return {word for word in words if model.vosk_model_find_word(word) < 0}


def audit_georgian(path: Path = AUDIT_PATH) -> dict[str, object]:
    if not CATALOG_PATH.is_file():
        raise FileNotFoundError("App catalog is missing; run scan-apps first")
    entries = load_catalog()
    custom = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    all_aliases = [alias for aliases in custom.values() for alias in aliases]
    missing_words = probe_missing_words(_words(all_aliases), "ka")

    covered: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    uncovered: list[str] = []
    catalog_names = {entry.name for entry in entries}

    for entry in entries:
        aliases = custom.get(entry.name, [])
        valid_aliases: list[str] = []
        invalid_aliases: list[dict[str, object]] = []
        for alias in aliases:
            alias_words = _words([alias])
            rejected = sorted(alias_words & missing_words)
            if alias_words and not rejected:
                valid_aliases.append(alias)
            elif alias_words:
                invalid_aliases.append({"alias": alias, "missing_words": rejected})
        if valid_aliases:
            covered.append({"app": entry.name, "valid_aliases": valid_aliases})
        else:
            uncovered.append(entry.name)
        if invalid_aliases:
            invalid.append({"app": entry.name, "invalid_aliases": invalid_aliases})

    aliases_without_app = sorted(name for name in custom if name not in catalog_names)
    report: dict[str, object] = {
        "language": "ka",
        "catalog_entries": len(entries),
        "covered_entries": len(covered),
        "uncovered_entries": len(uncovered),
        "missing_words": sorted(missing_words),
        "covered": covered,
        "invalid": invalid,
        "uncovered": uncovered,
        "aliases_without_catalog_match": aliases_without_app,
    }
    atomic_write_text(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report

