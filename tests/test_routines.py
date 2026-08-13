import json

import pytest

from voice_assistant import routines
from voice_assistant.catalog import CatalogEntry
from voice_assistant.routines import Routine, execute_routine, load_routines, routine_phrases, save_routines


def _catalog(path) -> None:
    path.write_text(
        json.dumps(
            [
                {"name": "Google Chrome", "aliases": ["ქრომი"], "launch_type": "app_id", "launch_value": "chrome"},
                {"name": "Discord", "aliases": ["დისქორდი"], "launch_type": "app_id", "launch_value": "discord"},
            ]
        ),
        encoding="utf-8",
    )


def test_routine_round_trip_and_phrases(tmp_path, monkeypatch) -> None:
    catalog = tmp_path / "apps.json"
    path = tmp_path / "routines.json"
    english = tmp_path / "english_aliases.json"
    _catalog(catalog)
    english.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(routines, "USER_CONFIG_ROOT", tmp_path)
    routine = Routine("Work", {"ka": ["სამუშაო რეჟიმი"], "en": ["work mode"]}, ["Google Chrome", "Discord"])

    save_routines([routine], path, catalog)

    assert load_routines(path, catalog) == [routine]
    assert routine_phrases("ka", path, catalog)["სამუშაო რეჟიმი"] == routine


def test_routine_rejects_missing_apps_and_conflicting_aliases(tmp_path, monkeypatch) -> None:
    catalog = tmp_path / "apps.json"
    english = tmp_path / "english_aliases.json"
    _catalog(catalog)
    english.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(routines, "USER_CONFIG_ROOT", tmp_path)

    with pytest.raises(ValueError, match="missing apps"):
        save_routines([Routine("Bad", {"ka": ["ჩემი რეჟიმი"]}, ["Missing App"])], tmp_path / "r.json", catalog)
    with pytest.raises(ValueError, match="conflicts"):
        save_routines([Routine("Bad", {"ka": ["გახსენი ქრომი"]}, ["Google Chrome"])], tmp_path / "r.json", catalog)
    with pytest.raises(ValueError, match="conflicts"):
        save_routines([Routine("Bad", {"ka": ["ქრომი გახსენი"]}, ["Google Chrome"])], tmp_path / "r.json", catalog)


def test_execute_routine_launches_catalog_entries_in_order(monkeypatch) -> None:
    entries = [
        CatalogEntry("Chrome", ["chrome"], "app_id", "chrome"),
        CatalogEntry("Discord", ["discord"], "app_id", "discord"),
    ]
    launched = []
    monkeypatch.setattr(routines, "launch_verified", lambda entry: launched.append(entry.name))
    monkeypatch.setattr(routines.time, "sleep", lambda seconds: None)

    detail = execute_routine(Routine("Work", {"en": ["work"]}, ["Chrome", "Discord"]), entries)

    assert launched == ["Chrome", "Discord"]
    assert detail == "Chrome, Discord"
