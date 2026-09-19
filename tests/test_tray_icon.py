from voice_assistant.tray import TrayApplication, create_icon_image
from voice_assistant import tray


def test_tray_icon_renders_rgba_at_windows_tray_size() -> None:
    image = create_icon_image("sleeping")
    assert image.mode == "RGBA"
    assert image.size == (64, 64)


def test_text_files_open_explicitly_in_notepad(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("voice_assistant.tray.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    path = tmp_path / "settings.json"

    TrayApplication._open_text_file(path)

    assert path.is_file()
    assert calls[0][0][0] == ["notepad.exe", str(path)]
    assert calls[0][1]["close_fds"] is True

def test_notes_window_opens_as_separate_process(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("voice_assistant.tray.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("voice_assistant.tray.sys.frozen", False, raising=False)

    TrayApplication._open_notes_window(None, None)

    assert calls[0][0][0][-2:] == ["-m", "voice_assistant.notes_window"]
    assert calls[0][1]["close_fds"] is True


def test_home_window_opens_as_separate_process(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr("voice_assistant.tray.find_home_bundle", lambda: tmp_path)
    monkeypatch.setattr("voice_assistant.tray.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("voice_assistant.tray.sys.frozen", False, raising=False)

    TrayApplication._open_home_window(None, None)

    assert calls[0][0][0][-3:] == ["-m", "voice_assistant.tray", "--home-window"]
    assert calls[0][1]["close_fds"] is True


def test_home_subcommands_dispatch_before_tray_lock(monkeypatch) -> None:
    import voice_assistant.home_catalog_launch as catalog_launch
    import voice_assistant.home_window as home_window

    seen = []
    monkeypatch.setattr(home_window, "main", lambda: seen.append("window") or 0)
    monkeypatch.setattr(catalog_launch, "main", lambda args: seen.append(args) or 0)

    monkeypatch.setattr(tray.sys, "argv", ["Gela.exe", "--home-window"])
    assert tray.main() == 0
    monkeypatch.setattr(tray.sys, "argv", ["Gela.exe", "--home-catalog-launch", "apps", "0" * 24, "result.json"])
    assert tray.main() == 0
    assert seen == ["window", ["apps", "0" * 24, "result.json"]]
