from pathlib import Path

import pytest

from voice_assistant import vocabulary


class FakeModel:
    def __init__(self, path: str) -> None:
        self.path = path

    def vosk_model_find_word(self, word: str) -> int:
        return {"known": 42, "გელა": 84}.get(word, -1)


def test_vocabulary_probe_uses_direct_model_lookup(monkeypatch) -> None:
    monkeypatch.setattr(vocabulary, "Model", FakeModel, raising=False)
    monkeypatch.setattr(vocabulary, "SetLogLevel", lambda _level: None, raising=False)
    monkeypatch.setattr(
        vocabulary,
        "load_settings",
        lambda: type("Settings", (), {"models": {"en": Path("english-model")}})(),
    )

    missing = vocabulary.probe_missing_words({"known", "unknown"}, "en")

    assert missing == {"unknown"}


def test_vocabulary_probe_rejects_an_unsupported_language() -> None:
    with pytest.raises(ValueError, match="Unsupported vocabulary language"):
        vocabulary.probe_missing_words({"known"}, "de")


def test_vocabulary_probe_skips_loading_a_model_for_empty_input(monkeypatch) -> None:
    monkeypatch.setattr(
        vocabulary,
        "Model",
        lambda _path: (_ for _ in ()).throw(AssertionError("model should not load")),
        raising=False,
    )

    assert vocabulary.probe_missing_words(set(), "ka") == set()
