from pathlib import Path

from voice_assistant import notes


def isolate_notes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(notes, "NOTES_RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(notes, "DRAFT_PATH", tmp_path / "runtime" / "draft.txt")
    monkeypatch.setattr(notes, "STATE_PATH", tmp_path / "runtime" / "state.json")


def test_dictation_session_state_and_utf8_transcript(monkeypatch, tmp_path) -> None:
    isolate_notes(monkeypatch, tmp_path)
    monkeypatch.setattr(notes, "launch_notes_window", lambda: None)

    notes.prepare_blank_note()
    assert notes.request_dictation_start() == "notes writing"
    assert notes.read_state()["active"] is True

    notes.append_transcript("გამარჯობა საქართველო")
    notes.append_transcript("hello world")
    assert notes.DRAFT_PATH.read_text(encoding="utf-8") == "გამარჯობა საქართველო hello world"

    assert notes.request_dictation_stop() == "notes stopped"
    assert notes.read_state()["active"] is False


def test_final_note_preserves_existing_desktop_copy(monkeypatch, tmp_path) -> None:
    isolate_notes(monkeypatch, tmp_path)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr(notes, "desktop_path", lambda: desktop)
    notes.prepare_blank_note()
    notes.append_transcript("ახალი ჩანაწერი")
    (desktop / "gela.txt").write_text("ძველი ჩანაწერი", encoding="utf-8")

    destination = notes.save_final_note()

    assert destination.read_text(encoding="utf-8") == "ახალი ჩანაწერი"
    backups = list(desktop.glob("gela_*.txt"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "ძველი ჩანაწერი"


def test_stop_phrase_is_removed_only_from_end() -> None:
    assert notes.split_stop_phrase("დღეს კარგია გელა შეწყვიტე წერა") == ("დღეს კარგია", True)
    assert notes.split_stop_phrase("გელა შეწყვიტე წერა") == ("", True)
    assert notes.split_stop_phrase("მე ვთქვი გელა შეწყვიტე წერა შემდეგ") == (
        "მე ვთქვი გელა შეწყვიტე წერა შემდეგ",
        False,
    )


def test_spoken_punctuation_and_language_detection() -> None:
    assert notes.format_dictation_text("გამარჯობა მძიმე როგორ ხარ კითხვის ნიშანი") == "გამარჯობა, როგორ ხარ?"
    assert notes.format_dictation_text("first line new line მეორე ხაზი წერტილი") == "first line\nმეორე ხაზი."
    assert notes.detected_language("ქართული text") == "ქართული + English"


def test_all_georgian_spoken_punctuation() -> None:
    transcript = (
        "ერთი მძიმე ორი წერტილი სამი კითხვის ნიშანი "
        "ოთხი ძახილის ნიშანი ხუთი მრავალ წერტილი სათაური ორი წერილი"
    )
    assert notes.format_dictation_text(transcript) == "ერთი, ორი. სამი? ოთხი! ხუთი... სათაური:"
    assert notes.format_dictation_text("სათაური ორი წერილი ტექსტი") == "სათაური: ტექსტი"
