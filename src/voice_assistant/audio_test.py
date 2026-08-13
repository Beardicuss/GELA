from __future__ import annotations

import json
from pathlib import Path
import wave

from vosk import KaldiRecognizer, Model, SetLogLevel

from .catalog import load_catalog, normalize_phrase
from .config import USER_CONFIG_ROOT, load_settings
from .recognizer import RecognitionResult, command_phrases, decode_result


def recognize_command_file(path: Path, language: str) -> tuple[RecognitionResult, str | None]:
    settings = load_settings()
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Test audio must be mono, 16-bit PCM WAV")
        if wav.getframerate() != settings.audio.sample_rate:
            raise ValueError(
                f"Test audio must be {settings.audio.sample_rate} Hz; got {wav.getframerate()} Hz"
            )
        chunks: list[bytes] = []
        while chunk := wav.readframes(settings.audio.block_size):
            chunks.append(chunk)

    entries = load_catalog()
    if language == "ka":
        phrases = command_phrases(entries, "ka")
    elif language == "en":
        aliases_path = USER_CONFIG_ROOT / "english_aliases.json"
        aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
        entries_by_name = {entry.name: entry for entry in entries}
        phrases = {
            normalize_phrase(alias): entries_by_name[name]
            for name, values in aliases.items()
            if name in entries_by_name
            for alias in values
        }
    else:
        raise ValueError(f"Unsupported language: {language}")

    SetLogLevel(-1)
    recognizer = KaldiRecognizer(
        Model(str(settings.models[language])),
        settings.audio.sample_rate,
        json.dumps([*sorted(phrases), "[unk]"], ensure_ascii=False),
    )
    recognizer.SetWords(True)
    result = RecognitionResult("", 0.0)
    for chunk in chunks:
        if recognizer.AcceptWaveform(chunk):
            candidate = decode_result(recognizer.Result())
            if candidate.text:
                result = candidate
    final = decode_result(recognizer.FinalResult())
    if final.text:
        result = final
    entry = phrases.get(result.text)
    return result, entry.name if entry else None
