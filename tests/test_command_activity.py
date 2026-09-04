from voice_assistant.command_activity import CommandActivityStore, board_text
from voice_assistant.remote_commands import RemoteCommandResult


def test_georgian_command_is_transliterated_for_board_font():
    assert board_text("გახსენი სთიმი") == "GAKHSENI STIMI"


def test_activity_store_exposes_latest_result_without_georgian_glyphs():
    store = CommandActivityStore()
    store.record("mobile", RemoteCommandResult("executed", "ჩართე ქრონიკები", "Chronicles", "ok"))
    activity = store.snapshot("sleeping")
    assert activity["source"] == "MOBILE"
    assert activity["transcript"] == "CHARTE KRONIKEBI"
    assert activity["matchedCommand"] == "CHRONICLES"
    assert activity["result"] == "COMPLETED"
