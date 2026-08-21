from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from .actions import SystemAction, build_action_phrases, execute_action
from .catalog import CatalogEntry, load_catalog, normalize_phrase
from .config import USER_CONFIG_ROOT
from .launcher import launch_verified
from .intent import expand_intent_phrases
from .recognizer import command_phrases
from .routines import Routine, execute_routine, routine_phrases


CommandTarget = CatalogEntry | SystemAction | Routine

WAKE_PREFIXES = tuple(
    sorted(
        {
            "gela",
            "hey gela",
            "hi gela",
            "hello gela",
            "გელა",
            "ჰეი გელა",
            "გამარჯობა გელა",
        },
        key=len,
        reverse=True,
    )
)


@dataclass(frozen=True)
class RemoteCommandResult:
    status: Literal["executed", "not-understood", "failed"]
    transcript: str
    matched_command: str | None
    message: str
    detail: str | None = None


def command_index(language: str) -> dict[str, CommandTarget]:
    if language not in {"ka", "en"}:
        raise ValueError("Language must be 'ka' or 'en'")
    entries = load_catalog()
    english_path = USER_CONFIG_ROOT / "english_aliases.json"
    english_aliases = (
        json.loads(english_path.read_text(encoding="utf-8"))
        if english_path.is_file()
        else {}
    )
    phrases: dict[str, CommandTarget] = dict(command_phrases(entries, language))
    phrases.update(build_action_phrases(entries, language, english_aliases))
    phrases.update(routine_phrases(language))
    return expand_intent_phrases(phrases, language)


def command_candidates(transcript: str) -> list[str]:
    """Return the command text with an optional assistant invocation removed."""
    normalized = normalize_phrase(transcript)
    if not normalized:
        return []
    candidates = [normalized]
    for prefix in WAKE_PREFIXES:
        if normalized == prefix:
            return candidates
        marker = f"{prefix} "
        if normalized.startswith(marker):
            candidates.insert(0, normalized[len(marker) :].strip())
            break
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def resolve_text_command(transcript: str, language: str) -> tuple[str | None, CommandTarget | None]:
    languages = [language, *(item for item in ("ka", "en") if item != language)]
    candidates = command_candidates(transcript)
    for candidate_language in languages:
        index = command_index(candidate_language)
        for candidate in candidates:
            target = index.get(candidate)
            if target is not None:
                return candidate, target
    return None, None


def execute_text_command(transcript: str, language: str = "ka") -> RemoteCommandResult:
    normalized = normalize_phrase(transcript)
    if not normalized:
        return RemoteCommandResult("not-understood", transcript, None, "The command was empty.")
    _matched_phrase, target = resolve_text_command(transcript, language)
    if target is None:
        return RemoteCommandResult(
            "not-understood", transcript, None, "Gela did not recognize that command."
        )
    try:
        if isinstance(target, SystemAction):
            detail = execute_action(target)
        elif isinstance(target, Routine):
            detail = execute_routine(target)
        else:
            detail = launch_verified(target)
    except Exception as exc:
        return RemoteCommandResult("failed", transcript, target.name, "Command execution failed.", str(exc))
    message = target.name if not detail else f"{target.name}: {detail.replace('_', ' ')}"
    return RemoteCommandResult("executed", transcript, target.name, message, detail)
