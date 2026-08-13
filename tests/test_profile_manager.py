import json

import pytest

from voice_assistant.alias_store import AliasStore
from voice_assistant.app_profiles import AppProfileStore, profile_for
from voice_assistant.profile_manager import save_profile_configuration


def make_stores(tmp_path):
    catalog = tmp_path / "apps.json"
    profiles = tmp_path / "app_profiles.json"
    ka = tmp_path / "aliases.json"
    en = tmp_path / "english_aliases.json"
    catalog.write_text(json.dumps([{"name": "Chrome"}, {"name": "Steam"}]), encoding="utf-8")
    profiles.write_text("{}", encoding="utf-8")
    ka.write_text("{}", encoding="utf-8")
    en.write_text("{}", encoding="utf-8")
    return AppProfileStore(catalog, profiles), AliasStore(catalog, ka, en), profiles, ka, en


def test_profile_manager_saves_controls_and_bilingual_aliases(monkeypatch, tmp_path) -> None:
    profile_store, alias_store, profiles, ka, en = make_stores(tmp_path)
    monkeypatch.setattr("voice_assistant.profile_manager.scan_catalog", lambda: [1, 2])

    count = save_profile_configuration(
        profile_store,
        alias_store,
        "Chrome",
        ["chrome.exe"],
        ["Chrome Workspace"],
        "graceful_only",
        ["ქრომი"],
        ["chrome"],
    )

    assert count == 2
    assert profile_for("Chrome", profiles).preferred_processes == ["chrome"]
    assert json.loads(ka.read_text(encoding="utf-8")) == {"Chrome": ["ქრომი"]}
    assert json.loads(en.read_text(encoding="utf-8")) == {"Chrome": ["chrome"]}


def test_profile_manager_rolls_back_every_file_on_catalog_failure(monkeypatch, tmp_path) -> None:
    profile_store, alias_store, profiles, ka, en = make_stores(tmp_path)
    monkeypatch.setattr(
        "voice_assistant.profile_manager.scan_catalog",
        lambda: (_ for _ in ()).throw(RuntimeError("scan failed")),
    )

    with pytest.raises(RuntimeError, match="scan failed"):
        save_profile_configuration(
            profile_store,
            alias_store,
            "Chrome",
            ["chrome"],
            ["Chrome Workspace"],
            "window_only",
            ["ქრომი"],
            ["chrome"],
        )

    assert json.loads(profiles.read_text(encoding="utf-8")) == {}
    assert json.loads(ka.read_text(encoding="utf-8")) == {}
    assert json.loads(en.read_text(encoding="utf-8")) == {}


def test_profile_manager_accepts_open_vocabulary_command_alias(monkeypatch, tmp_path) -> None:
    profile_store, alias_store, profiles, ka, _en = make_stores(tmp_path)
    monkeypatch.setattr("voice_assistant.profile_manager.scan_catalog", lambda: [1, 2])

    save_profile_configuration(
        profile_store,
        alias_store,
        "Chrome",
        ["chrome"],
        [],
        "graceful_then_force",
        ["უცნობი"],
        [],
    )

    assert json.loads(ka.read_text(encoding="utf-8")) == {"Chrome": ["უცნობი"]}
