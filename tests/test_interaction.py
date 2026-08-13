from dataclasses import dataclass

from voice_assistant.interaction import (
    CommandCandidate,
    choose_command_action,
    should_retry_command,
)


@dataclass(frozen=True)
class Entry:
    name: str


def candidate(confidence: float, name: str, language: str = "ka") -> CommandCandidate:
    return CommandCandidate(confidence, language, None, Entry(name))


def test_confident_unambiguous_command_executes() -> None:
    action, selected = choose_command_action([candidate(0.9, "Chrome")], 0.65, 0.12)
    assert action == "execute"
    assert selected.entry.name == "Chrome"


def test_low_confidence_valid_command_is_rejected() -> None:
    action, selected = choose_command_action([candidate(0.55, "Chrome")], 0.65, 0.12)
    assert (action, selected) == ("reject", None)


def test_close_competing_apps_require_confirmation() -> None:
    action, selected = choose_command_action(
        [candidate(0.90, "Word", "en"), candidate(0.84, "Movies", "ka")],
        0.65,
        0.12,
    )
    assert (action, selected) == ("reject", None)


def test_very_weak_candidate_is_rejected() -> None:
    action, selected = choose_command_action([candidate(0.3, "Chrome")], 0.65, 0.12)
    assert (action, selected) == ("reject", None)


def test_command_retry_is_bounded_to_one_extra_attempt() -> None:
    assert should_retry_command(attempt=1, retry_attempts=1)
    assert not should_retry_command(attempt=2, retry_attempts=1)
