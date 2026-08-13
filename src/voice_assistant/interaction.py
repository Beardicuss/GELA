from __future__ import annotations

from dataclasses import dataclass
from typing import Any


NO_PHRASES = frozenset({"არა", "გააუქმე", "გაუქმება"})
CANCEL_PHRASES = NO_PHRASES


@dataclass(frozen=True)
class CommandCandidate:
    confidence: float
    language: str
    result: Any
    entry: Any


def choose_command_action(
    candidates: list[CommandCandidate],
    execute_confidence: float,
    ambiguity_margin: float,
) -> tuple[str, CommandCandidate | None]:
    if not candidates:
        return "reject", None
    ranked = sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True)
    best = ranked[0]
    competing = next((item for item in ranked[1:] if item.entry != best.entry), None)
    ambiguous = competing is not None and best.confidence - competing.confidence <= ambiguity_margin
    if best.confidence >= execute_confidence and not ambiguous:
        return "execute", best
    return "reject", None


def should_retry_command(attempt: int, retry_attempts: int) -> bool:
    """Return whether a rejected command has another bounded attempt available."""
    return attempt <= retry_attempts
