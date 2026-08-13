import json

import pytest

from voice_assistant.alias_store import AliasStore


def make_store(tmp_path):
    catalog = tmp_path / "apps.json"
    ka = tmp_path / "aliases.json"
    en = tmp_path / "english_aliases.json"
    catalog.write_text(json.dumps([{"name": "Chrome"}, {"name": "Steam"}]), encoding="utf-8")
    ka.write_text("{}", encoding="utf-8")
    en.write_text("{}", encoding="utf-8")
    return AliasStore(catalog, ka, en), ka, en


def test_alias_store_add_remove_and_save(tmp_path) -> None:
    store, ka, _ = make_store(tmp_path)
    store.add("Chrome", "ka", "ქრომი")
    store.save()
    assert json.loads(ka.read_text(encoding="utf-8")) == {"Chrome": ["ქრომი"]}
    store.remove("Chrome", "ka", "ქრომი")
    assert store.aliases("Chrome", "ka") == []


def test_alias_store_rejects_cross_app_duplicate(tmp_path) -> None:
    store, _, _ = make_store(tmp_path)
    store.add("Chrome", "en", "browser")
    with pytest.raises(ValueError, match="Chrome"):
        store.add("Steam", "en", "Browser")


def test_alias_store_replaces_one_apps_aliases_atomically(tmp_path) -> None:
    store, _, _ = make_store(tmp_path)
    store.add("Chrome", "en", "browser")
    store.add("Steam", "en", "games")

    store.replace("Chrome", "en", ["web", "internet"])

    assert store.aliases("Chrome", "en") == ["web", "internet"]
    with pytest.raises(ValueError, match="Steam"):
        store.replace("Chrome", "en", ["games"])
    assert store.aliases("Chrome", "en") == ["web", "internet"]
