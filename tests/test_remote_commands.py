from voice_assistant.actions import SystemAction
from voice_assistant.remote_commands import command_candidates, execute_text_command


def test_execute_text_command_rejects_unknown(monkeypatch):
    monkeypatch.setattr("voice_assistant.remote_commands.command_index", lambda language: {})
    result = execute_text_command("not a command", "en")
    assert result.status == "not-understood"
    assert result.matched_command is None


def test_execute_text_command_uses_existing_action_executor(monkeypatch):
    action = SystemAction("Volume Up", "volume_up")
    monkeypatch.setattr("voice_assistant.remote_commands.command_index", lambda language: {"volume up": action})
    calls = []
    monkeypatch.setattr("voice_assistant.remote_commands.execute_action", lambda target: calls.append(target) or None)
    result = execute_text_command(" Volume UP ", "en")
    assert result.status == "executed"
    assert result.matched_command == "Volume Up"
    assert calls == [action]


def test_command_candidates_remove_latin_gela_wake_word():
    assert command_candidates("Gela, გახსენი სტიმი") == ["გახსენი სტიმი", "gela გახსენი სტიმი"]


def test_command_candidates_remove_georgian_gela_wake_word():
    assert command_candidates("გელა! გახსენი სტიმი") == ["გახსენი სტიმი", "გელა გახსენი სტიმი"]


def test_execute_text_command_falls_back_to_english(monkeypatch):
    action = SystemAction("Volume Up", "volume_up")
    monkeypatch.setattr(
        "voice_assistant.remote_commands.command_index",
        lambda language: {"volume up": action} if language == "en" else {},
    )
    calls = []
    monkeypatch.setattr("voice_assistant.remote_commands.execute_action", lambda target: calls.append(target) or None)

    result = execute_text_command("Gela, volume up", "ka")

    assert result.status == "executed"
    assert result.matched_command == "Volume Up"
    assert calls == [action]


def test_mobile_command_does_not_require_wake_word(monkeypatch):
    action = SystemAction("Shut down computer", "power_shutdown")
    monkeypatch.setattr(
        "voice_assistant.remote_commands.command_index",
        lambda language: {"გამორთე კომპიუტერი": action} if language == "ka" else {},
    )
    calls = []
    monkeypatch.setattr(
        "voice_assistant.remote_commands.execute_action",
        lambda target: calls.append(target) or "shutdown scheduled in 5 seconds",
    )

    result = execute_text_command("გამორთე კომპიუტერი", "ka")

    assert result.status == "executed"
    assert result.matched_command == "Shut down computer"
    assert calls == [action]


def test_remote_command_safely_corrects_board_transcription(monkeypatch):
    steam = SystemAction("Open Steam", "open_steam")
    monkeypatch.setattr(
        "voice_assistant.remote_commands.command_index",
        lambda language: {"გახსენი სთიმი": steam} if language == "ka" else {},
    )
    monkeypatch.setattr("voice_assistant.remote_commands.execute_action", lambda target: None)

    result = execute_text_command("გელა გახსენის თიმი", "ka")

    assert result.status == "executed"
    assert result.matched_command == "Open Steam"
