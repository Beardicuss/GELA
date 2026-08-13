from pathlib import Path

from voice_assistant.startup import _powershell_single_quoted


def test_powershell_single_quoted_escapes_apostrophes() -> None:
    assert _powershell_single_quoted(Path("C:/Dan'Te/Gela")) == "C:\\Dan''Te\\Gela"
