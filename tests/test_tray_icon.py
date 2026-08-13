from voice_assistant.tray import TrayApplication, create_icon_image


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
