from pathlib import Path

from voice_assistant.command_recognizer import (
    COMMAND_MODEL_FILES,
    OmnilingualCommandRecognizer,
    validate_command_model_directory,
)


class _FakeResult:
    text = "  გახსენი, მისტფოლი! "


class _FakeStream:
    def __init__(self) -> None:
        self.result = _FakeResult()
        self.accepted = None

    def accept_waveform(self, sample_rate, samples) -> None:
        self.accepted = (sample_rate, samples)


class _FakeRecognizer:
    def __init__(self) -> None:
        self.stream = _FakeStream()

    def create_stream(self):
        return self.stream

    def decode_stream(self, stream) -> None:
        assert stream is self.stream


def _model_directory(tmp_path: Path) -> Path:
    for name in COMMAND_MODEL_FILES:
        (tmp_path / name).write_bytes(b"model")
    return tmp_path


def test_command_model_normalizes_text_and_uses_16khz(monkeypatch, tmp_path) -> None:
    fake = _FakeRecognizer()
    monkeypatch.setattr(
        "voice_assistant.command_recognizer.sherpa_onnx.OfflineRecognizer.from_omnilingual_asr_ctc",
        lambda **_kwargs: fake,
    )
    recognizer = OmnilingualCommandRecognizer(_model_directory(tmp_path))

    result = recognizer.transcribe_pcm16(b"\x00\x00\xff\x7f")

    assert result.text == "გახსენი მისტფოლი"
    assert result.confidence == 1.0
    assert fake.stream.accepted[0] == 16_000
    assert len(fake.stream.accepted[1]) == 2


def test_command_model_directory_requires_both_files(tmp_path) -> None:
    try:
        validate_command_model_directory(tmp_path)
    except FileNotFoundError as exc:
        assert "model.int8.onnx" in str(exc)
    else:
        raise AssertionError("Incomplete command model was accepted")
