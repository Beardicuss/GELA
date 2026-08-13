from __future__ import annotations

from array import array
import logging
from pathlib import Path
import sys

import sherpa_onnx

from .catalog import normalize_phrase
from .recognizer import RecognitionResult


COMMAND_MODEL_FILES = ("model.int8.onnx", "tokens.txt")


def validate_command_model_directory(path: Path) -> None:
    missing = [name for name in COMMAND_MODEL_FILES if not (path / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Command model directory is incomplete: {path}; missing: {', '.join(missing)}"
        )


class OmnilingualCommandRecognizer:
    """Offline multilingual CTC recognizer used only after the wake gate."""

    def __init__(self, model_path: Path, *, num_threads: int = 2) -> None:
        validate_command_model_directory(model_path)
        self.model_path = model_path
        self.sample_rate = 16_000
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_omnilingual_asr_ctc(
            model=str(model_path / COMMAND_MODEL_FILES[0]),
            tokens=str(model_path / COMMAND_MODEL_FILES[1]),
            num_threads=max(1, min(int(num_threads), 4)),
            decoding_method="greedy_search",
            provider="cpu",
        )

    def transcribe_pcm16(self, audio: bytes) -> RecognitionResult:
        if len(audio) < 2:
            return RecognitionResult("", 0.0)
        if len(audio) % 2:
            audio = audio[:-1]
        pcm = array("h")
        pcm.frombytes(audio)
        if sys.byteorder != "little":
            pcm.byteswap()
        samples = [sample / 32768.0 for sample in pcm]
        stream = self._recognizer.create_stream()
        stream.accept_waveform(self.sample_rate, samples)
        self._recognizer.decode_stream(stream)
        text = normalize_phrase(stream.result.text)
        logging.info(
            "Omnilingual command transcription: %s (audio=%.2fs)",
            text or "[nothing]",
            len(pcm) / self.sample_rate,
        )
        # The CTC result has no calibrated utterance probability. Exact phrase
        # matching against Gela's fixed action/catalog allowlist remains the
        # execution boundary.
        return RecognitionResult(text, 1.0 if text else 0.0)
