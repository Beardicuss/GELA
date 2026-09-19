from types import SimpleNamespace

from voice_assistant import alias_manager


class FakeEntry:
    def __init__(self) -> None:
        self.value = ""

    def selection_present(self) -> bool:
        return False

    def insert(self, _position, value: str) -> None:
        self.value += value


def test_georgian_key_bypasses_tk_question_mark(monkeypatch) -> None:
    entry = FakeEntry()
    monkeypatch.setattr(alias_manager, "windows_unicode_key", lambda keycode: "გ" if keycode == 71 else None)

    result = alias_manager.AliasManagerWindow._insert_georgian_key(
        SimpleNamespace(keycode=71), entry
    )

    assert result == "break"
    assert entry.value == "გ"


def test_non_georgian_key_keeps_normal_tk_handling(monkeypatch) -> None:
    entry = FakeEntry()
    monkeypatch.setattr(alias_manager, "windows_unicode_key", lambda _keycode: None)

    result = alias_manager.AliasManagerWindow._insert_georgian_key(
        SimpleNamespace(keycode=65), entry
    )

    assert result is None
    assert entry.value == ""
