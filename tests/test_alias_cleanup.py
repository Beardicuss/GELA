import json

from voice_assistant.alias_cleanup import synchronize_alias_files


def _write(path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_missing_app_aliases_are_archived_and_restored(tmp_path) -> None:
    georgian = tmp_path / "aliases.json"
    english = tmp_path / "english_aliases.json"
    archive = tmp_path / "alias_archive.json"
    _write(georgian, {"Chrome": ["ქრომი"], "Telegram Desktop": ["ტელეგრამი"]})
    _write(english, {})

    removed = synchronize_alias_files({"Chrome"}, georgian, english, archive)

    assert removed.archived == {"ka": ["Telegram Desktop"], "en": []}
    assert json.loads(georgian.read_text(encoding="utf-8")) == {"Chrome": ["ქრომი"]}
    assert json.loads(archive.read_text(encoding="utf-8"))["ka"] == {
        "Telegram Desktop": ["ტელეგრამი"]
    }

    restored = synchronize_alias_files({"Chrome", "Telegram Desktop"}, georgian, english, archive)

    assert restored.restored == {"ka": ["Telegram Desktop"], "en": []}
    assert json.loads(georgian.read_text(encoding="utf-8"))["Telegram Desktop"] == ["ტელეგრამი"]
    assert json.loads(archive.read_text(encoding="utf-8"))["ka"] == {}


def test_restore_keeps_conflicting_alias_safely_archived(tmp_path) -> None:
    georgian = tmp_path / "aliases.json"
    english = tmp_path / "english_aliases.json"
    archive = tmp_path / "alias_archive.json"
    _write(georgian, {"Chrome": ["ბრაუზერი"]})
    _write(english, {})
    _write(archive, {"ka": {"Telegram Desktop": ["ბრაუზერი"]}, "en": {}})

    report = synchronize_alias_files(
        {"Chrome", "Telegram Desktop"}, georgian, english, archive
    )

    assert report.restored == {"ka": [], "en": []}
    assert "Telegram Desktop" not in json.loads(georgian.read_text(encoding="utf-8"))
    assert json.loads(archive.read_text(encoding="utf-8"))["ka"] == {
        "Telegram Desktop": ["ბრაუზერი"]
    }
