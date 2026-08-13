from __future__ import annotations

from typing import Any

from .catalog import CatalogEntry, normalize_phrase


KA_REVERSIBLE_VERBS = frozenset(
    {"გახსენი", "ჩართე", "გაუშვი", "დახურე", "გამორთე", "მაჩვენე", "დამალე", "გაზარდე", "აღადგინე"}
)
KA_OPEN_VERBS = frozenset({"გახსენი", "ჩართე", "გაუშვი"})


def _variants(phrase: str, target: Any, language: str) -> set[str]:
    phrase = normalize_phrase(phrase)
    variants: set[str] = set()
    if language == "ka":
        variants.update({f"გთხოვ {phrase}", f"თუ შეიძლება {phrase}", f"ახლა {phrase}"})
        first, separator, remainder = phrase.partition(" ")
        if separator and first in KA_REVERSIBLE_VERBS:
            variants.add(f"{remainder} {first}")
        if separator and first in KA_OPEN_VERBS:
            variants.update({f"შეგიძლია {remainder} გახსნა", f"მინდა {remainder} გახსნა"})
    elif language == "en":
        variants.update({f"please {phrase}", f"{phrase} please", f"can you {phrase}"})
        if isinstance(target, CatalogEntry):
            variants.update({f"open {phrase}", f"launch {phrase}", f"start {phrase}"})
    else:
        raise ValueError(f"Unsupported intent language: {language}")
    return {normalize_phrase(value) for value in variants if normalize_phrase(value)}


def expand_intent_phrases(phrases: dict[str, Any], language: str) -> dict[str, Any]:
    """Add bounded natural variants without overriding or guessing ambiguous commands."""
    result = dict(phrases)
    generated: dict[str, Any] = {}
    blocked: set[str] = set()
    for phrase, target in phrases.items():
        for variant in _variants(phrase, target, language):
            if variant in result or variant in blocked:
                continue
            previous = generated.get(variant)
            if previous is not None and previous != target:
                generated.pop(variant, None)
                blocked.add(variant)
            else:
                generated[variant] = target
    result.update(generated)
    return result
