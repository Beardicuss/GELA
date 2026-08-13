import json

import pytest

from voice_assistant.alias_store import AliasStore
from voice_assistant.recognition_test_window import promote_recognition_result
from voice_assistant.recognizer import RecognitionResult


def make_store(tmp_path) -> tuple[AliasStore, object]:
    catalog = tmp_path / "apps.json"
    ka = tmp_path / "aliases.json"
    en = tmp_path / "english_aliases.json"
    catalog.write_text(json.dumps([{"name": "Chrome"}, {"name": "Steam"}]), encoding="utf-8")
    ka.write_text("{}", encoding="utf-8")
    en.write_text("{}", encoding="utf-8")
    return AliasStore(catalog, ka, en), ka


def test_recognized_result_is_promoted_through_alias_store(monkeypatch, tmp_path) -> None:
    store, ka_path = make_store(tmp_path)
    scans = []
    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.probe_missing_words",
        lambda words, language: set(),
    )
    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.scan_catalog",
        lambda: scans.append(True),
    )

    alias = promote_recognition_result(
        store,
        "Chrome",
        "ka",
        RecognitionResult("ქრომი", 0.88),
    )

    assert alias == "ქრომი"
    assert json.loads(ka_path.read_text(encoding="utf-8")) == {"Chrome": ["ქრომი"]}
    assert scans == [True]


def test_low_confidence_or_missing_vocabulary_cannot_be_promoted(monkeypatch, tmp_path) -> None:
    store, _ka_path = make_store(tmp_path)
    with pytest.raises(ValueError, match="დაბალია"):
        promote_recognition_result(store, "Chrome", "ka", RecognitionResult("ქრომი", 0.3))

    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.probe_missing_words",
        lambda words, language: {"ქრომი"},
    )
    with pytest.raises(ValueError, match="ლექსიკაში"):
        promote_recognition_result(store, "Chrome", "ka", RecognitionResult("ქრომი", 0.9))


def test_promotion_rejects_unknown_app_and_cross_app_duplicate(monkeypatch, tmp_path) -> None:
    store, _ka_path = make_store(tmp_path)
    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.probe_missing_words",
        lambda words, language: set(),
    )
    monkeypatch.setattr("voice_assistant.recognition_test_window.scan_catalog", lambda: [])
    with pytest.raises(ValueError, match="კატალოგში"):
        promote_recognition_result(store, "Unknown", "ka", RecognitionResult("ქრომი", 0.9))

    promote_recognition_result(store, "Chrome", "ka", RecognitionResult("ქრომი", 0.9))
    with pytest.raises(ValueError, match="Chrome"):
        promote_recognition_result(store, "Steam", "ka", RecognitionResult("ქრომი", 0.9))


def test_catalog_failure_rolls_back_new_alias(monkeypatch, tmp_path) -> None:
    store, ka_path = make_store(tmp_path)
    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.probe_missing_words",
        lambda words, language: set(),
    )
    monkeypatch.setattr(
        "voice_assistant.recognition_test_window.scan_catalog",
        lambda: (_ for _ in ()).throw(RuntimeError("scan failed")),
    )

    with pytest.raises(RuntimeError, match="scan failed"):
        promote_recognition_result(
            store,
            "Chrome",
            "ka",
            RecognitionResult("ქრომი", 0.9),
        )

    assert json.loads(ka_path.read_text(encoding="utf-8")) == {}
