from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json

from .alias_store import ENGLISH_ALIASES_PATH
from .catalog import ALIASES_PATH, load_catalog, normalize_phrase


STATUS_LABELS = {
    "both_ready": "ქართული + English",
    "ka_ready": "ქართული მზადაა",
    "en_ready": "English მზადაა",
    "invalid": "არასწორი ხმოვანი სახელი",
    "unconfigured": "ხმოვანი სახელი არ აქვს",
}


@dataclass(frozen=True)
class VoiceReadiness:
    app_name: str
    status: str
    valid_ka_aliases: list[str]
    valid_en_aliases: list[str]
    invalid_aliases: list[str]


def _alias_words(aliases: list[str]) -> set[str]:
    return {
        word
        for alias in aliases
        for word in normalize_phrase(alias).split()
        if word
    }


def _partition_aliases(aliases: list[str], missing_words: set[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for alias in aliases:
        words = set(normalize_phrase(alias).split())
        if words and not words.intersection(missing_words):
            valid.append(alias)
        elif words:
            invalid.append(alias)
    return valid, invalid


def classify_voice_readiness(
    app_names: list[str],
    georgian_aliases: dict[str, list[str]],
    english_aliases: dict[str, list[str]],
    *,
    missing_ka: set[str],
    missing_en: set[str],
) -> list[VoiceReadiness]:
    records: list[VoiceReadiness] = []
    for app_name in sorted(set(app_names), key=str.casefold):
        ka_values = georgian_aliases.get(app_name, [])
        en_values = english_aliases.get(app_name, [])
        valid_ka, invalid_ka = _partition_aliases(ka_values, missing_ka)
        valid_en, invalid_en = _partition_aliases(en_values, missing_en)
        if valid_ka and valid_en:
            status = "both_ready"
        elif valid_ka:
            status = "ka_ready"
        elif valid_en:
            status = "en_ready"
        elif ka_values or en_values:
            status = "invalid"
        else:
            status = "unconfigured"
        records.append(
            VoiceReadiness(
                app_name,
                status,
                valid_ka,
                valid_en,
                [*invalid_ka, *invalid_en],
            )
        )
    return records


def analyze_voice_readiness() -> list[VoiceReadiness]:
    entries = load_catalog()
    georgian = json.loads(ALIASES_PATH.read_text(encoding="utf-8")) if ALIASES_PATH.is_file() else {}
    english = (
        json.loads(ENGLISH_ALIASES_PATH.read_text(encoding="utf-8"))
        if ENGLISH_ALIASES_PATH.is_file()
        else {}
    )
    return classify_voice_readiness(
        [entry.name for entry in entries],
        georgian,
        english,
        missing_ka=set(),
        missing_en=set(),
    )


def readiness_counts(records: list[VoiceReadiness]) -> Counter[str]:
    return Counter(record.status for record in records)
