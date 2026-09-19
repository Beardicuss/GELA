from voice_assistant.notes_window import (
    STATUS_LISTENING,
    STATUS_STOPPED,
    STATUS_WRITING,
    NotesWindow,
)


class FakeVariable:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class FakeButton:
    def __init__(self) -> None:
        self.visible = False

    def pack(self, **_kwargs) -> None:
        self.visible = True

    def pack_forget(self) -> None:
        self.visible = False


def notes_shell() -> NotesWindow:
    window = object.__new__(NotesWindow)
    window.status_var = FakeVariable()
    window.stop_button = FakeButton()
    window.dictation_active = False
    return window


def test_stop_button_is_only_visible_during_dictation() -> None:
    window = notes_shell()

    window.set_dictation_active(True)
    assert window.status_var.value == STATUS_LISTENING
    assert window.stop_button.visible

    window.set_writing()
    assert window.status_var.value == STATUS_WRITING

    window.set_dictation_active(False)
    assert window.status_var.value == STATUS_STOPPED
    assert not window.stop_button.visible
