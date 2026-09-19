from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path

from .catalog import normalize_phrase
from .config import USER_CONFIG_ROOT
from .storage import atomic_write_text


CORRECTIONS_PATH = USER_CONFIG_ROOT / "dictation_corrections.json"
MAX_CORRECTIONS = 500
MAX_PHRASE_LENGTH = 120


@dataclass(frozen=True)
class DictationCorrection:
    heard: str
    replacement: str


def _clean(value: str) -> str:
    return " ".join(value.split())


def validate_corrections(corrections: list[DictationCorrection]) -> None:
    if len(corrections) > MAX_CORRECTIONS:
        raise ValueError(f"At most {MAX_CORRECTIONS} dictation corrections are allowed")
    seen: set[str] = set()
    for correction in corrections:
        heard = normalize_phrase(correction.heard)
        replacement = _clean(correction.replacement)
        if not heard or not replacement:
            raise ValueError("Heard and replacement phrases cannot be empty")
        if len(heard) > MAX_PHRASE_LENGTH or len(replacement) > MAX_PHRASE_LENGTH:
            raise ValueError(f"Correction phrases cannot exceed {MAX_PHRASE_LENGTH} characters")
        if heard in seen:
            raise ValueError(f"Duplicate heard phrase: {correction.heard}")
        seen.add(heard)


def load_corrections(path: Path = CORRECTIONS_PATH) -> list[DictationCorrection]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("corrections", [])
        corrections = [
            DictationCorrection(_clean(str(item["heard"])), _clean(str(item["replacement"])))
            for item in items
        ]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Dictation corrections file is invalid: {exc}") from exc
    validate_corrections(corrections)
    return corrections


def save_corrections(
    corrections: list[DictationCorrection],
    path: Path = CORRECTIONS_PATH,
) -> None:
    normalized = [
        DictationCorrection(normalize_phrase(item.heard), _clean(item.replacement))
        for item in corrections
    ]
    validate_corrections(normalized)
    normalized.sort(key=lambda item: item.heard.casefold())
    atomic_write_text(
        path,
        json.dumps(
            {"corrections": [asdict(item) for item in normalized]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def apply_corrections(text: str, corrections: list[DictationCorrection]) -> str:
    """Apply longest phrase matches once, without recursively rewriting replacements."""
    words = text.split()
    if not words or not corrections:
        return text
    rules = sorted(
        ((normalize_phrase(item.heard).split(), item.replacement) for item in corrections),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    output: list[str] = []
    index = 0
    while index < len(words):
        match = next(
            (
                (tokens, replacement)
                for tokens, replacement in rules
                if words[index : index + len(tokens)] == tokens
            ),
            None,
        )
        if match is None:
            output.append(words[index])
            index += 1
            continue
        tokens, replacement = match
        output.append(replacement)
        index += len(tokens)
    return " ".join(output)


class CorrectionCache:
    def __init__(self, path: Path = CORRECTIONS_PATH) -> None:
        self.path = path
        self._signature: tuple[int, int, int] | None = None
        self._corrections: list[DictationCorrection] = []

    def apply(self, text: str) -> str:
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        except OSError:
            signature = None
        if signature != self._signature:
            self._signature = signature
            try:
                self._corrections = load_corrections(self.path)
            except (OSError, ValueError):
                logging.exception("Ignoring invalid dictation corrections file: %s", self.path)
        return apply_corrections(text, self._corrections)
