from __future__ import annotations

import pytest

from voice_assistant.catalog import CatalogEntry
from voice_assistant import home_catalog_launch
from voice_assistant.home_catalog_launch import entry_id, find_entry, kind_for


def test_catalog_categories_and_ids() -> None:
    app = CatalogEntry("Editor", [], "app_id", "Vendor.Editor")
    game = CatalogEntry("Game", [], "uri", "steam://rungameid/123")
    media = CatalogEntry("Song", [], "file", "C:/Music/Song.mp3")
    browser = CatalogEntry("Google Chrome", [], "app_id", "Chrome")
    chrome_app = CatalogEntry("Squoosh", [], "app_id", "Chrome._crx_example")
    other = CatalogEntry("Web", [], "uri", "https://example.test")

    assert [kind_for(item) for item in (app, game, media, browser, chrome_app, other)] == [
        "apps", "games", "media", "browsers", "apps", None
    ]
    assert len({entry_id(item) for item in (app, game, media, browser, chrome_app, other)}) == 6
    assert find_entry("games", entry_id(game), [app, game, media]) == game
    assert find_entry("browsers", entry_id(browser), [browser]) == browser
    assert find_entry("apps", entry_id(browser), [browser]) == browser


def test_catalog_selection_rejects_forged_or_changed_entries() -> None:
    original = CatalogEntry("Editor", [], "app_id", "Vendor.Editor")
    changed = CatalogEntry("Editor", [], "app_id", "Vendor.Other")
    with pytest.raises(ValueError):
        find_entry("apps", entry_id(original), [changed])
    with pytest.raises(ValueError):
        find_entry("games", entry_id(original), [original])
    with pytest.raises(ValueError):
        find_entry("apps", "not-an-id", [original])


def test_windowed_launch_writes_result_file_without_stdout(tmp_path, monkeypatch) -> None:
    app = CatalogEntry("Editor", [], "app_id", "Vendor.Editor")
    calls = []
    monkeypatch.setattr(home_catalog_launch, "load_catalog", lambda: [app])
    monkeypatch.setattr(home_catalog_launch, "launch_verified", lambda entry: calls.append(entry) or "verified")
    path = tmp_path / "result.json"

    assert home_catalog_launch.main(["apps", entry_id(app), str(path)]) == 0
    assert calls == [app]
    assert '"ok": true' in path.read_text(encoding="utf-8")

    assert home_catalog_launch.main(["apps", "0" * 24, str(path)]) == 1
    assert calls == [app]
    assert '"ok": false' in path.read_text(encoding="utf-8")
