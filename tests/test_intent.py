from dataclasses import dataclass

from voice_assistant.catalog import CatalogEntry
from voice_assistant.intent import expand_intent_phrases


@dataclass(frozen=True)
class Action:
    name: str


def test_georgian_intent_expands_word_order_and_politeness() -> None:
    chrome = Action("Chrome")
    expanded = expand_intent_phrases({"გახსენი ქრომი": chrome}, "ka")

    assert expanded["ქრომი გახსენი"] is chrome
    assert expanded["გთხოვ გახსენი ქრომი"] is chrome
    assert expanded["თუ შეიძლება გახსენი ქრომი"] is chrome
    assert expanded["შეგიძლია ქრომი გახსნა"] is chrome
    assert expanded["მინდა ქრომი გახსნა"] is chrome


def test_english_catalog_alias_gains_open_variants() -> None:
    steam = CatalogEntry("Steam", ["steam"], "app_id", "steam")
    expanded = expand_intent_phrases({"steam": steam}, "en")

    assert expanded["open steam"] is steam
    assert expanded["please steam"] is steam


def test_generated_variant_never_overrides_exact_command() -> None:
    exact = Action("Exact")
    source = Action("Source")
    expanded = expand_intent_phrases(
        {"გახსენი ქრომი": source, "ქრომი გახსენი": exact},
        "ka",
    )

    assert expanded["ქრომი გახსენი"] is exact
