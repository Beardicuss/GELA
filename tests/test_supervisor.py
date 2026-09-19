from pathlib import Path

from voice_assistant import supervisor


def test_source_child_command_uses_tray_module(monkeypatch) -> None:
    monkeypatch.delattr(supervisor.sys, "frozen", raising=False)
    monkeypatch.setattr(supervisor.sys, "executable", "C:/Python/python.exe")
    monkeypatch.setattr(supervisor.sys, "platform", "win32")

    assert supervisor._child_command() == [
        str(Path("C:/Python/pythonw.exe")),
        "-m",
        "voice_assistant.tray",
        "--supervised-child",
    ]


def test_frozen_child_command_reuses_gela_executable(monkeypatch) -> None:
    monkeypatch.setattr(supervisor.sys, "frozen", True, raising=False)
    monkeypatch.setattr(supervisor.sys, "executable", "C:/Gela/Gela.exe")

    assert supervisor._child_command() == ["C:/Gela/Gela.exe", "--supervised-child"]


def test_intentional_exit_marker_only_written_for_supervised_child(tmp_path, monkeypatch) -> None:
    marker = tmp_path / "intentional_exit"
    monkeypatch.setattr(supervisor, "INTENTIONAL_EXIT_PATH", marker)
    monkeypatch.delenv("GELA_SUPERVISED", raising=False)

    supervisor.mark_intentional_exit()
    assert not marker.exists()

    monkeypatch.setenv("GELA_SUPERVISED", "1")
    supervisor.mark_intentional_exit()
    assert marker.is_file()
