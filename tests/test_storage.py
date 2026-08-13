import errno

from voice_assistant import storage


def test_replace_file_falls_back_for_cross_volume_virtualization(tmp_path, monkeypatch) -> None:
    source = tmp_path / "settings.json.tmp"
    destination = tmp_path / "settings.json"
    source.write_text("new settings", encoding="utf-8")

    def cross_volume(*args) -> None:
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr(storage.os, "replace", cross_volume)
    storage.replace_file(source, destination)

    assert destination.read_text(encoding="utf-8") == "new settings"
    assert not source.exists()
