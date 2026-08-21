import json

import pytest

from voice_assistant import actions
from voice_assistant.actions import (
    SystemAction,
    _close_process_windows,
    _infer_process_names,
    _validated_process_names,
    build_action_phrases,
    execute_action,
)
from voice_assistant.catalog import CatalogEntry


@pytest.fixture(autouse=True)
def isolated_learned_targets(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(actions, "LEARNED_TARGETS_PATH", tmp_path / "learned_process_targets.json")
    monkeypatch.setattr(actions, "GAME_STATE_PATH", tmp_path / "game_lifecycle.json")
    profiles = tmp_path / "app_profiles.json"
    profiles.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(actions, "PROFILE_PATH", profiles)


def test_static_georgian_actions_are_routed() -> None:
    phrases = build_action_phrases([], "ka")
    assert phrases["ხმა აუწიე"].action_id == "volume_up"
    assert phrases["ხმას აუწიე"].action_id == "volume_up"
    assert phrases["ხმა გათიშე"].action_id == "volume_mute"
    assert phrases["გადაიღე ეკრანი"].action_id == "screenshot"
    assert phrases["ჩაკეტე კომპიუტერი"].action_id == "lock_windows"
    assert phrases["გამორთე კომპიუტერი"].action_id == "power_shutdown"
    assert phrases["დაარესტარტე კომპიუტერი"].action_id == "power_restart"
    assert phrases["დააძინე კომპიუტერი"].action_id == "power_sleep"
    assert phrases["გახსენი ვაიფაი"].value == "ms-settings:network-wifi"
    assert phrases["ჩართე ვაიფაი"] == SystemAction("Turn on Wi-Fi", "radio", "WiFi:on")
    assert phrases["გამორთე ბლუთუზი"].value == "Bluetooth:off"
    assert phrases["აჩვენე ყველა ფანჯარა"].value == "win+tab"
    assert phrases["სიკაშკაშე გაზარდე"].value == "10"
    assert phrases["შემდეგი სიმღერა"].value == "next"
    assert phrases["გააგრძელე მუსიკა"].value == "play_pause"
    assert phrases["ჩაკეცე"].value == "minimize"
    assert phrases["ამოკეცე"].value == "restore"
    assert phrases["გაადიდე"].value == "maximize"
    assert phrases["დააპატარავე"].value == "restore"
    assert phrases["ჩართე ფრენის რეჟიმი"].value == "on"


def test_allowlisted_close_phrases_use_catalog_aliases(monkeypatch, tmp_path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps({"Google Chrome": ["chrome"]}), encoding="utf-8")
    monkeypatch.setattr("voice_assistant.actions.PROCESS_TARGETS_PATH", targets)
    chrome = CatalogEntry("Google Chrome", ["ქრომი"], "app_id", "Chrome")
    phrases = build_action_phrases([chrome], "ka")
    close = phrases["დახურე ქრომი"]
    assert close.name == "Google Chrome"
    assert close.action_id == "close_app"
    assert json.loads(close.value) == {"name": "Google Chrome", "processes": ["chrome"]}


def test_close_rejects_non_allowlist_process_syntax() -> None:
    with pytest.raises(ValueError, match="Invalid allowlisted"):
        _close_process_windows("chrome;Remove-Item")


def test_named_window_commands_use_allowlisted_catalog_aliases(monkeypatch, tmp_path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps({"Google Chrome": ["chrome"]}), encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", targets)
    chrome = CatalogEntry("Google Chrome", ["ქრომი"], "app_id", "Chrome")

    phrases = build_action_phrases([chrome], "ka")

    assert phrases["გადადი ქრომი"].action_id == "window_focus"
    assert phrases["დამალე ქრომი"].action_id == "window_minimize"
    assert phrases["ჩაკეცე ქრომი"].action_id == "window_minimize"
    assert phrases["გაადიდე ქრომი"].action_id == "window_maximize"
    assert phrases["ამოკეცე ქრომი"].action_id == "window_restore"
    assert json.loads(phrases["გაზარდე ქრომი"].value) == {
        "name": "Google Chrome",
        "processes": ["chrome"],
    }


def test_close_phrases_cover_catalog_without_manual_process_mapping(monkeypatch, tmp_path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", targets)
    calculator = CatalogEntry("Calculator", ["კალკულატორი"], "app_id", "Microsoft.Calculator!App")

    phrases = build_action_phrases([calculator], "ka")

    target = json.loads(phrases["დახურე კალკულატორი"].value)
    assert target == {"name": "Calculator", "processes": []}
    assert phrases["გამორთე კალკულატორი"].action_id == "close_app"
    assert phrases["გათიშე კალკულატორი"].action_id == "close_app"


def test_window_phrases_cover_catalog_without_manual_process_mapping(monkeypatch, tmp_path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", targets)
    chatgpt = CatalogEntry("ChatGPT", ["კოდექსი"], "app_id", "OpenAI.Codex!App")

    phrases = build_action_phrases([chatgpt], "ka")

    assert phrases["დამალე კოდექსი"].action_id == "window_minimize"
    assert phrases["გაზარდე კოდექსი"].action_id == "window_maximize"
    assert phrases["აღადგინე კოდექსი"].action_id == "window_restore"
    assert json.loads(phrases["დამალე კოდექსი"].value) == {
        "name": "ChatGPT",
        "processes": [],
    }


def test_steam_game_actions_are_marked_for_lifecycle_safety(monkeypatch, tmp_path) -> None:
    targets = tmp_path / "targets.json"
    targets.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", targets)
    game = CatalogEntry(
        "ELDEN RING NIGHTREIGN",
        ["ნაითრეინი"],
        "uri",
        "steam://rungameid/2622380",
        ["nightreign"],
    )

    target = json.loads(build_action_phrases([game], "ka")["გამორთე ნაითრეინი"].value)

    assert target == {
        "name": "ELDEN RING NIGHTREIGN",
        "processes": ["nightreign"],
        "kind": "steam_game",
    }


def test_executable_process_name_is_inferred_from_catalog_entry() -> None:
    entry = CatalogEntry("Unity", ["unity"], "app_id", r"D:\Unity\Editor\Unity.exe")
    assert _infer_process_names(entry) == ["Unity"]


def test_dotted_executable_process_name_is_not_truncated() -> None:
    entry = CatalogEntry(
        "Unity Bug Reporter",
        ["unity bug reporter"],
        "app_id",
        r"D:\Unity\2017.4.40f1\Editor\BugReporter\unity.bugreporter.exe",
    )

    assert _infer_process_names(entry) == ["unity.bugreporter"]


def test_named_window_control_calls_only_validated_operation(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(actions, "_control_window", lambda action_id, value: calls.append((action_id, value)))

    execute_action(SystemAction("Chrome", "window_restore", "chrome"))

    assert calls == [("window_restore", "chrome")]
    assert _validated_process_names("chrome|msedge.exe") == {"chrome", "msedge"}
    with pytest.raises(ValueError, match="Invalid allowlisted"):
        _validated_process_names("chrome;calc")


def test_catalog_window_control_falls_back_to_title(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(actions, "_matching_title_windows", lambda name: [4321] if name == "ChatGPT" else [])
    monkeypatch.setattr(actions, "_show_window", lambda hwnd, operation: calls.append((hwnd, operation)))

    target = json.dumps({"name": "ChatGPT", "processes": []})
    actions._control_window("window_minimize", target)

    assert calls == [(4321, "minimize")]


def test_newly_learned_process_is_used_without_rebuilding_actions(monkeypatch, tmp_path) -> None:
    defaults = tmp_path / "targets.json"
    learned = tmp_path / "learned.json"
    defaults.write_text("{}", encoding="utf-8")
    learned.write_text(json.dumps({"ChatGPT": ["codex"]}), encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", defaults)
    monkeypatch.setattr(actions, "LEARNED_TARGETS_PATH", learned)
    found = []
    monkeypatch.setattr(actions, "_find_window_for_processes", lambda value: found.append(value) or 42)

    target = json.dumps({"name": "ChatGPT", "processes": []})
    assert actions._find_catalog_window(target) == 42

    assert found == ["codex"]


def test_newly_learned_process_is_used_for_complete_close(monkeypatch, tmp_path) -> None:
    defaults = tmp_path / "targets.json"
    learned = tmp_path / "learned.json"
    defaults.write_text("{}", encoding="utf-8")
    learned.write_text(json.dumps({"ChatGPT": ["codex"]}), encoding="utf-8")
    monkeypatch.setattr(actions, "PROCESS_TARGETS_PATH", defaults)
    monkeypatch.setattr(actions, "LEARNED_TARGETS_PATH", learned)
    closed = []
    monkeypatch.setattr(actions, "_close_process_windows", closed.append)

    target = json.dumps({"name": "ChatGPT", "processes": []})
    detail = actions._close_catalog_app(target)

    assert detail == "verified processes exited=codex"
    assert closed == ["codex"]


def test_game_close_uses_gameplay_process_but_never_launcher_or_anticheat(monkeypatch, tmp_path) -> None:
    lifecycle = tmp_path / "game_lifecycle.json"
    lifecycle.write_text(
        json.dumps(
            {
                "Nightreign": {
                    "app_id": "steam://rungameid/2622380",
                    "state": "running",
                    "launcher_processes": ["steam", "steamwebhelper"],
                    "anti_cheat_processes": ["easyanticheat_eos"],
                    "game_processes": ["nightreign"],
                    "updated_at": "2026-01-01T00:00:00+04:00",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(actions, "GAME_STATE_PATH", lifecycle)
    closed = []
    monkeypatch.setattr(actions, "_close_process_windows", closed.append)
    target = json.dumps(
        {
            "name": "Nightreign",
            "processes": ["steam", "start_protected_game", "nightreign"],
            "kind": "steam_game",
        }
    )

    detail = actions._close_catalog_app(target)

    assert detail == "verified processes exited=nightreign"
    assert closed == ["nightreign"]
    assert json.loads(lifecycle.read_text(encoding="utf-8"))["Nightreign"]["state"] == "stopped"


def test_already_stopped_game_clears_stale_lifecycle(monkeypatch, tmp_path) -> None:
    lifecycle = tmp_path / "game_lifecycle.json"
    lifecycle.write_text(
        json.dumps(
            {
                "Nightreign": {
                    "app_id": "steam://rungameid/2622380",
                    "state": "running",
                    "launcher_processes": ["steam"],
                    "anti_cheat_processes": [],
                    "game_processes": ["nightreign"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(actions, "GAME_STATE_PATH", lifecycle)
    monkeypatch.setattr(
        actions,
        "_close_process_windows",
        lambda value: (_ for _ in ()).throw(RuntimeError("Application is not running")),
    )
    monkeypatch.setattr(
        actions,
        "_close_title_windows",
        lambda value: (_ for _ in ()).throw(
            RuntimeError("Application is not running or its window could not be identified")
        ),
    )
    target = json.dumps(
        {"name": "Nightreign", "processes": ["nightreign"], "kind": "steam_game"}
    )

    assert actions._close_catalog_app(target) == "state already_stopped app=Nightreign"
    assert json.loads(lifecycle.read_text(encoding="utf-8"))["Nightreign"]["state"] == "stopped"


def test_profile_preferred_process_overrides_payload_and_learned_targets(monkeypatch, tmp_path) -> None:
    actions.PROFILE_PATH.write_text(
        json.dumps(
            {
                "ChatGPT": {
                    "preferred_processes": ["preferred"],
                    "window_titles": [],
                    "close_behavior": "graceful_then_force",
                }
            }
        ),
        encoding="utf-8",
    )
    actions.LEARNED_TARGETS_PATH.write_text(
        json.dumps({"ChatGPT": ["learned"]}), encoding="utf-8"
    )
    closed = []
    monkeypatch.setattr(actions, "_close_process_windows", closed.append)

    detail = actions._close_catalog_app(
        json.dumps({"name": "ChatGPT", "processes": ["payload"]})
    )

    assert detail == "verified processes exited=preferred"
    assert closed == ["preferred"]


def test_profile_graceful_only_disables_force_close(monkeypatch) -> None:
    actions.PROFILE_PATH.write_text(
        json.dumps(
            {
                "ChatGPT": {
                    "preferred_processes": ["codex"],
                    "window_titles": [],
                    "close_behavior": "graceful_only",
                }
            }
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        actions,
        "_close_process_windows",
        lambda value, **kwargs: calls.append((value, kwargs)),
    )

    actions._close_catalog_app(json.dumps({"name": "ChatGPT", "processes": []}))

    assert calls == [("codex", {"allow_force": False})]


def test_profile_window_only_never_targets_a_process(monkeypatch) -> None:
    actions.PROFILE_PATH.write_text(
        json.dumps(
            {
                "ChatGPT": {
                    "preferred_processes": ["codex"],
                    "window_titles": ["Codex Workspace"],
                    "close_behavior": "window_only",
                }
            }
        ),
        encoding="utf-8",
    )
    closed_titles = []
    monkeypatch.setattr(
        actions,
        "_close_process_windows",
        lambda value: (_ for _ in ()).throw(AssertionError("process close must not run")),
    )
    monkeypatch.setattr(
        actions,
        "_close_title_windows",
        lambda app, titles: closed_titles.append((app, titles)),
    )

    detail = actions._close_catalog_app(
        json.dumps({"name": "ChatGPT", "processes": ["codex"]})
    )

    assert detail == "verified window closed=ChatGPT"
    assert closed_titles == [("ChatGPT", ["Codex Workspace"])]


def test_settings_action_accepts_only_fixed_settings_uri(monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(actions.os, "startfile", opened.append)

    execute_action(SystemAction("Wi-Fi", "open_uri", "ms-settings:network-wifi"))

    assert opened == ["ms-settings:network-wifi"]
    with pytest.raises(ValueError, match="Settings URIs"):
        execute_action(SystemAction("Unsafe", "open_uri", "https://example.com"))


def test_power_actions_use_only_fixed_windows_operations(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(actions, "hidden_process_kwargs", lambda: {"creationflags": 7})
    monkeypatch.setattr(
        actions.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    assert execute_action(SystemAction("Shutdown", "power_shutdown")) == "shutdown scheduled in 5 seconds"
    assert execute_action(SystemAction("Restart", "power_restart")) == "restart scheduled in 5 seconds"

    assert calls == [
        (["shutdown.exe", "/s", "/t", "5"], {"check": True, "creationflags": 7}),
        (["shutdown.exe", "/r", "/t", "5"], {"check": True, "creationflags": 7}),
    ]


def test_sleep_action_uses_windows_suspend_api(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        actions.ctypes.windll.powrprof,
        "SetSuspendState",
        lambda hibernate, force, disable_wake: calls.append(
            (hibernate, force, disable_wake)
        ) or True,
    )

    assert execute_action(SystemAction("Sleep", "power_sleep")) == "sleep requested"
    assert calls == [(False, False, False)]


def test_brightness_action_is_limited_to_ten_percent(monkeypatch) -> None:
    monkeypatch.setattr(actions, "_adjust_brightness", lambda delta: 70 if delta == 10 else 50)

    assert execute_action(SystemAction("Brightness", "brightness", "10")) == "brightness=70%"
    with pytest.raises(ValueError):
        actions._press_hotkey("win+r")


def test_media_control_uses_only_fixed_media_keys(monkeypatch) -> None:
    pressed = []
    monkeypatch.setattr(actions, "_press_media_key", pressed.append)

    execute_action(SystemAction("Next track", "media_key", "next"))
    execute_action(SystemAction("Play", "media_key", "play_pause"))

    assert pressed == [0xB0, 0xB3]
    with pytest.raises(ValueError, match="media control"):
        actions._control_media("volume_destroy")


def test_radio_control_uses_only_fixed_kind_and_state(monkeypatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return actions.subprocess.CompletedProcess(command, 0, "WiFi=On\n", "")

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    assert execute_action(SystemAction("Wi-Fi", "radio", "WiFi:on")) == "WiFi=On"
    assert calls[0][0][:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert calls[0][1]["capture_output"] is True
    with pytest.raises(ValueError, match="radio control"):
        actions._set_radio("Airplane:toggle")


def test_radio_control_reports_missing_hardware(monkeypatch) -> None:
    monkeypatch.setattr(
        actions.subprocess,
        "run",
        lambda *args, **kwargs: actions.subprocess.CompletedProcess(args[0], 4, "", ""),
    )
    with pytest.raises(RuntimeError, match="Bluetooth radio was not found"):
        actions._set_radio("Bluetooth:on")


def test_radio_control_reports_already_requested_state(monkeypatch) -> None:
    monkeypatch.setattr(
        actions.subprocess,
        "run",
        lambda *args, **kwargs: actions.subprocess.CompletedProcess(
            args[0], 0, "already=Bluetooth:Off\n", ""
        ),
    )

    assert actions._set_radio("Bluetooth:off") == "state already_off radio=Bluetooth"


def test_flight_mode_controls_only_wifi_and_bluetooth(monkeypatch) -> None:
    requested = []

    def fake_set_radio(value: str) -> str:
        requested.append(value)
        return value

    monkeypatch.setattr(actions, "_set_radio", fake_set_radio)

    assert actions._set_airplane_mode("on") == "flight_mode=on"
    assert requested == ["WiFi:off", "Bluetooth:off"]


def test_catalog_close_falls_back_to_window_title(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(actions, "_matching_title_process_names", lambda name: [])
    monkeypatch.setattr(actions, "_close_title_windows", calls.append)

    detail = actions._close_catalog_app(json.dumps({"name": "Calculator", "processes": []}))

    assert calls == ["Calculator"]
    assert detail == "verified window closed=Calculator"


def test_catalog_close_uses_title_when_packaged_process_ignores_close(monkeypatch) -> None:
    calls = []
    attempts = []

    def close_process(value):
        attempts.append(value)
        if len(attempts) == 1:
            raise RuntimeError("Application is waiting for confirmation or unsaved work")

    monkeypatch.setattr(actions, "_close_process_windows", close_process)
    monkeypatch.setattr(actions, "_matching_title_process_names", lambda name: [])
    monkeypatch.setattr(actions, "_close_title_windows", calls.append)

    detail = actions._close_catalog_app(
        json.dumps({"name": "Calculator", "processes": ["CalculatorApp"]})
    )

    assert calls == ["Calculator"]
    assert attempts == ["CalculatorApp", "CalculatorApp"]
    assert detail == "verified processes exited=CalculatorApp"


def test_catalog_close_discovers_process_from_visible_window(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(actions, "_matching_title_process_names", lambda name: ["ChatGPT"])
    monkeypatch.setattr(actions, "_close_process_windows", calls.append)

    detail = actions._close_catalog_app(json.dumps({"name": "ChatGPT", "processes": []}))

    assert calls == ["ChatGPT"]
    assert detail == "verified processes exited=ChatGPT"


def test_catalog_close_reports_already_stopped(monkeypatch) -> None:
    monkeypatch.setattr(actions, "_matching_title_process_names", lambda name: [])
    monkeypatch.setattr(
        actions,
        "_close_title_windows",
        lambda name: (_ for _ in ()).throw(
            RuntimeError("Application is not running or its window could not be identified")
        ),
    )

    detail = actions._close_catalog_app(json.dumps({"name": "ChatGPT", "processes": []}))

    assert detail == "state already_stopped app=ChatGPT"
