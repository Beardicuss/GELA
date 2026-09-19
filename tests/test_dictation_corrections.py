import json

import pytest

from voice_assistant.dictation_corrections import (
    CorrectionCache,
    DictationCorrection,
    apply_corrections,
    load_corrections,
    save_corrections,
)


def test_longest_phrase_wins_without_recursive_replacement() -> None:
    rules = [
        DictationCorrection("ახალი", "ძველი"),
        DictationCorrection("ახალი სიტყვა", "სწორი ფრაზა"),
        DictationCorrection("სწორი", "არასწორი"),
    ]
    assert apply_corrections("ეს ახალი სიტყვა და ახალი", rules) == "ეს სწორი ფრაზა და ძველი"


def test_correction_matches_only_complete_words() -> None:
    rules = [DictationCorrection("კაცი", "ადამიანი")]
    assert apply_corrections("კაცი კაციშვილი", rules) == "ადამიანი კაციშვილი"


def test_save_and_load_preserve_georgian(tmp_path) -> None:
    path = tmp_path / "corrections.json"
    save_corrections([DictationCorrection("არასწორი", "სწორი")], path)
    assert load_corrections(path) == [DictationCorrection("არასწორი", "სწორი")]
    assert "არასწორი" in path.read_text(encoding="utf-8")


def test_duplicate_heard_phrase_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        save_corrections(
            [DictationCorrection("ერთი", "1"), DictationCorrection("ერთი", "one")],
            tmp_path / "corrections.json",
        )


def test_cache_reloads_after_file_change(tmp_path) -> None:
    path = tmp_path / "corrections.json"
    path.write_text(json.dumps({"corrections": []}), encoding="utf-8")
    cache = CorrectionCache(path)
    assert cache.apply("ტესტი") == "ტესტი"
    save_corrections([DictationCorrection("ტესტი", "შემოწმება")], path)
    assert cache.apply("ტესტი") == "შემოწმება"


def test_cache_keeps_last_valid_rules_when_file_is_damaged(tmp_path) -> None:
    path = tmp_path / "corrections.json"
    save_corrections([DictationCorrection("ტესტი", "შემოწმება")], path)
    cache = CorrectionCache(path)
    assert cache.apply("ტესტი") == "შემოწმება"
    path.write_text("{damaged", encoding="utf-8")
    assert cache.apply("ტესტი") == "შემოწმება"
