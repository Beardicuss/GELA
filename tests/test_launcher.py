import json

import pytest

from voice_assistant import launcher
from voice_assistant.catalog import CatalogEntry


def _clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(launcher.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))


@pytest.fixture(autouse=True)
def isolated_process_learning(monkeypatch, tmp_path) -> None:
    defaults = tmp_path / "process_targets.json"
    defaults.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "PROCESS_TARGETS_PATH", defaults)
    monkeypatch.setattr(launcher, "LEARNED_TARGETS_PATH", tmp_path / "learned_process_targets.json")
    monkeypatch.setattr(launcher, "GAME_STATE_PATH", tmp_path / "game_lifecycle.json")
    profiles = tmp_path / "app_profiles.json"
    profiles.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "PROFILE_PATH", profiles)


def test_verified_game_launch_waits_for_discovered_process(monkeypatch) -> None:
    _clock(monkeypatch)
    entry = CatalogEntry(
        "ELDEN RING NIGHTREIGN",
        ["ნაითრეინი"],
        "uri",
        "steam://rungameid/2622380",
        ["nightreign"],
    )
    process_checks = [0]
    launched = []

    def running_processes():
        process_checks[0] += 1
        return {"nightreign"} if process_checks[0] >= 3 else set()

    monkeypatch.setattr(launcher, "_running_process_names", running_processes)
    monkeypatch.setattr(launcher, "_visible_windows", lambda: {})
    monkeypatch.setattr(launcher, "launch", lambda target: launched.append(target.name))

    detail = launcher.launch_verified(entry, game_timeout=2)

    assert launched == [entry.name]
    assert detail == "verified stable process=nightreign"
    learned = json.loads(launcher.LEARNED_TARGETS_PATH.read_text(encoding="utf-8"))
    assert learned == {"ELDEN RING NIGHTREIGN": ["nightreign"]}


def test_verified_store_app_launch_accepts_matching_window(monkeypatch) -> None:
    _clock(monkeypatch)
    entry = CatalogEntry("ChatGPT", ["კოდექსი"], "app_id", "OpenAI.Codex!App")
    window_checks = [0]
    monkeypatch.setattr(launcher, "_running_process_names", lambda: set())

    def visible_windows():
        window_checks[0] += 1
        return {42: "ChatGPT"} if window_checks[0] >= 2 else {}

    monkeypatch.setattr(launcher, "_visible_windows", visible_windows)
    monkeypatch.setattr(launcher, "launch", lambda target: None)

    assert launcher.launch_verified(entry, app_timeout=2) == "verified stable window=ChatGPT"


def test_unverified_launch_reports_failure(monkeypatch) -> None:
    _clock(monkeypatch)
    entry = CatalogEntry("Missing Game", ["missing"], "uri", "steam://rungameid/1", ["missinggame"])
    monkeypatch.setattr(launcher, "_running_process_names", lambda: set())
    monkeypatch.setattr(launcher, "_visible_windows", lambda: {})
    monkeypatch.setattr(launcher, "launch", lambda target: None)

    with pytest.raises(RuntimeError, match="dispatched but not verified"):
        launcher.launch_verified(entry, game_timeout=0.5)


def test_already_running_process_skips_duplicate_launch(monkeypatch) -> None:
    entry = CatalogEntry("Chrome", ["ქრომი"], "app_id", "Chrome", ["chrome"])
    launched = []
    monkeypatch.setattr(launcher, "_running_process_names", lambda: {"chrome"})
    monkeypatch.setattr(launcher, "_visible_windows", lambda: {})
    monkeypatch.setattr(launcher, "launch", lambda target: launched.append(target.name))

    detail = launcher.launch_verified(entry)

    assert detail == "state already_running process=chrome"
    assert launched == []
    assert not launcher.LEARNED_TARGETS_PATH.exists()


def test_launcher_preserves_a_dotted_executable_process_name(monkeypatch) -> None:
    entry = CatalogEntry(
        "Unity Bug Reporter",
        ["unity bug reporter"],
        "app_id",
        r"D:\Unity\2017.4.40f1\Editor\BugReporter\unity.bugreporter.exe",
    )
    monkeypatch.setattr(launcher, "process_targets_for", lambda *_args: [])

    assert launcher._configured_process_names(entry) == {"unity.bugreporter"}


def test_verified_new_matching_window_learns_its_new_process(monkeypatch) -> None:
    _clock(monkeypatch)
    entry = CatalogEntry("ChatGPT", ["კოდექსი"], "app_id", "OpenAI.Codex!App")
    process_checks = [0]
    window_checks = [0]

    def running_processes():
        process_checks[0] += 1
        return set() if process_checks[0] == 1 else {"codex"}

    def visible_windows():
        window_checks[0] += 1
        return {} if window_checks[0] == 1 else {42: "ChatGPT"}

    monkeypatch.setattr(launcher, "_running_process_names", running_processes)
    monkeypatch.setattr(launcher, "_visible_windows", visible_windows)
    monkeypatch.setattr(launcher, "_window_process_name", lambda hwnd: "codex" if hwnd == 42 else None)
    monkeypatch.setattr(launcher, "launch", lambda target: None)

    detail = launcher.launch_verified(entry, app_timeout=2)

    assert detail == "verified stable window=ChatGPT"
    learned = json.loads(launcher.LEARNED_TARGETS_PATH.read_text(encoding="utf-8"))
    assert learned == {"ChatGPT": ["codex"]}


def test_existing_shared_window_process_is_not_learned(monkeypatch) -> None:
    _clock(monkeypatch)
    entry = CatalogEntry("Web App", ["web app"], "app_id", "Web.App!App")
    monkeypatch.setattr(launcher, "_running_process_names", lambda: {"chrome"})
    window_checks = [0]

    def visible_windows():
        window_checks[0] += 1
        return {} if window_checks[0] == 1 else {42: "Web App - Chrome"}

    monkeypatch.setattr(launcher, "_visible_windows", visible_windows)
    monkeypatch.setattr(launcher, "_window_process_name", lambda hwnd: "chrome")
    monkeypatch.setattr(launcher, "launch", lambda target: None)

    assert launcher.launch_verified(entry, app_timeout=2) == "verified stable window=Web App - Chrome"
    assert not launcher.LEARNED_TARGETS_PATH.exists()


def test_profile_process_and_window_title_override_automatic_guesses(monkeypatch, tmp_path) -> None:
    launcher.PROFILE_PATH.write_text(
        json.dumps(
            {
                "Custom App": {
                    "preferred_processes": ["preferred_app"],
                    "window_titles": ["Special Workspace"],
                    "close_behavior": "graceful_only",
                }
            }
        ),
        encoding="utf-8",
    )
    entry = CatalogEntry("Custom App", ["custom"], "app_id", "Other.Guess.exe")

    assert launcher._configured_process_names(entry) == {"preferred_app"}
    assert launcher._title_matches(entry, "Special Workspace — Document", ["Special Workspace"])
