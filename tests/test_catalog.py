import json
from pathlib import Path

from voice_assistant import catalog
from voice_assistant.catalog import (
    CatalogEntry,
    _disambiguate_names,
    _steam_executable_names,
    alias_index,
    normalize_phrase,
)


def test_steam_process_discovery_excludes_launch_and_setup_helpers(tmp_path) -> None:
    game = tmp_path / "Game"
    anticheat = game / "easyanticheat"
    anticheat.mkdir(parents=True)
    (game / "nightreign.exe").touch()
    (game / "start_protected_game.exe").touch()
    (anticheat / "easyanticheat_eos_setup.exe").touch()

    assert _steam_executable_names(tmp_path) == ["nightreign"]
from voice_assistant.recognizer import command_phrases


def test_normalize_phrase_removes_symbols() -> None:
    assert normalize_phrase("DARK SOULS™ III") == "dark souls iii"


def test_voice_commands_map_to_allowlisted_entry() -> None:
    chrome = CatalogEntry("Google Chrome", ["chrome"], "app_id", "chrome-id")
    phrases = command_phrases([chrome], "en")
    assert phrases["open chrome"] is chrome
    assert alias_index([chrome])["google chrome"] is chrome


def test_georgian_alias_maps_to_voice_command() -> None:
    chrome = CatalogEntry("Google Chrome", ["ქრომი"], "app_id", "chrome-id")
    phrases = command_phrases([chrome], "ka")
    assert phrases["გახსენი ქრომი"] is chrome


def test_mistfall_spoken_form_has_decoder_safe_georgian_alias() -> None:
    root = Path(__file__).resolve().parents[1]
    aliases = json.loads((root / "config" / "aliases.json").read_text(encoding="utf-8"))

    assert "მისთ ფოლი" in aliases["Mistfall Hunter"]


def test_scan_does_not_rewrite_unchanged_catalog(tmp_path, monkeypatch) -> None:
    entry = CatalogEntry("Google Chrome", ["chrome"], "app_id", "chrome-id")
    monkeypatch.setattr(catalog, "_start_apps", lambda: [entry])
    monkeypatch.setattr(catalog, "_steam_games", lambda: [])
    monkeypatch.setattr(catalog, "_media_files", lambda: [])
    monkeypatch.setattr(catalog, "ALIASES_PATH", tmp_path / "missing-aliases.json")
    output = tmp_path / "apps.json"

    _, first_changed = catalog.scan_catalog_with_status(output)
    first_mtime = output.stat().st_mtime_ns
    _, second_changed = catalog.scan_catalog_with_status(output)

    assert first_changed is True
    assert second_changed is False
    assert output.stat().st_mtime_ns == first_mtime


def test_windows_app_scan_uses_no_console_window(monkeypatch) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return type("Result", (), {"stdout": "[]"})()

    monkeypatch.setattr(catalog.subprocess, "run", fake_run)
    monkeypatch.setattr(catalog, "hidden_process_kwargs", lambda: {"creationflags": 0x08000000})

    assert catalog._start_apps() == []
    assert captured["creationflags"] == 0x08000000


def test_duplicate_catalog_names_receive_stable_descriptive_qualifiers() -> None:
    entries = [
        CatalogEntry("Unity", ["unity"], "app_id", r"D:\Unity\6000.4.6f1\Editor\Unity.exe"),
        CatalogEntry("Unity", ["unity"], "app_id", r"D:\Unity\2017.4.40f1\Editor\Unity.exe"),
        CatalogEntry("Uninstall", ["uninstall"], "app_id", r"D:\Apps\PC Remote Receiver\uninst.exe"),
        CatalogEntry("Uninstall", ["uninstall"], "app_id", r"C:\Ubisoft\Ubisoft Game Launcher\Uninstall.exe"),
        CatalogEntry("Get Help", ["get help"], "app_id", "http://java.com/help"),
        CatalogEntry("Get Help", ["get help"], "app_id", "Microsoft.GetHelp_8wekyb3d8bbwe!App"),
    ]

    result = _disambiguate_names(entries)
    names = {entry.name for entry in result}

    assert "Unity (6000.4.6f1)" in names
    assert "Unity (2017.4.40f1)" in names
    assert "Uninstall (PC Remote Receiver)" in names
    assert "Uninstall (Ubisoft Game Launcher)" in names
    assert "Get Help (java.com)" in names
    assert "Get Help (Microsoft Store)" in names
    assert len({normalize_phrase(entry.name) for entry in result}) == len(result)
    assert all("unity" not in entry.aliases for entry in result if entry.name.startswith("Unity"))


def test_media_scan_only_catalogs_allowlisted_extensions(tmp_path) -> None:
    library = tmp_path / "Playlists"
    library.mkdir()
    playlist = library / "Chronicles of the Fallen World.xspf"
    playlist.write_text("playlist", encoding="utf-8")
    (library / "notes.txt").write_text("ignored", encoding="utf-8")

    assert catalog._media_files((library,)) == [
        CatalogEntry(
            "Chronicles of the Fallen World",
            ["chronicles of the fallen world"],
            "file",
            str(playlist.resolve()),
        )
    ]


def test_media_file_must_be_supported_and_inside_allowlist(tmp_path) -> None:
    library = tmp_path / "Playlists"
    library.mkdir()
    playlist = library / "Chronicles.xspf"
    playlist.touch()
    outside = tmp_path / "Outside.xspf"
    outside.touch()
    text_file = library / "notes.txt"
    text_file.touch()

    assert catalog.is_allowed_media_file(playlist, (library,)) is True
    assert catalog.is_allowed_media_file(outside, (library,)) is False
    assert catalog.is_allowed_media_file(text_file, (library,)) is False


def test_chronicles_playlist_uses_correct_georgian_command() -> None:
    playlist = CatalogEntry(
        "Chronicles of the Fallen World",
        ["ქრონიკები"],
        "file",
        r"C:\Users\User\Music\Playlists\Chronicles of the Fallen World.xspf",
    )

    phrases = command_phrases([playlist], "ka")

    assert phrases["ჩართე ქრონიკები"] is playlist
    assert phrases["დაუკარი ქრონიკები"] is playlist


def test_georgian_mp3_filename_becomes_direct_play_command() -> None:
    track = CatalogEntry(
        "დაღლილი კაცი",
        ["დაღლილი კაცი"],
        "file",
        r"C:\Users\User\Music\Playlists\დაღლილი კაცი.mp3",
    )

    phrases = command_phrases([track], "ka")

    assert phrases["ჩართე დაღლილი კაცი"] is track
    assert phrases["დაუკარი დაღლილი კაცი"] is track
