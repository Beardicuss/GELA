from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import wave


VOICE_SAMPLE_RATE = 48_000
VOICE_CHANNELS = 1
VOICE_SAMPLE_WIDTH = 2
VOICE_COMPRESSION = "NONE"


@dataclass(frozen=True)
class VoiceAssetReport:
    expected_files: int
    valid_files: int
    errors: list[str]


def validate_processed_voice_assets(
    manifest_path: Path,
    processed_root: Path,
) -> VoiceAssetReport:
    errors: list[str] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    filenames = [row.get("processed_filename", "").strip() for row in rows]
    events = [row.get("event", "").strip() for row in rows]
    if any(not filename for filename in filenames):
        errors.append("Manifest contains an empty processed filename")
    if len(filenames) != len(set(filenames)):
        errors.append("Manifest contains duplicate processed filenames")
    if len(events) != len(set(events)):
        errors.append("Manifest contains duplicate response events")

    expected = {filename for filename in filenames if filename}
    actual = {path.name for path in processed_root.glob("*.wav")}
    for filename in sorted(expected - actual, key=str.casefold):
        errors.append(f"Missing processed response: {filename}")
    for filename in sorted(actual - expected, key=str.casefold):
        errors.append(f"Orphaned processed response: {filename}")

    valid = 0
    for filename in sorted(expected & actual, key=str.casefold):
        path = processed_root / filename
        try:
            with wave.open(str(path), "rb") as recording:
                channels = recording.getnchannels()
                sample_rate = recording.getframerate()
                sample_width = recording.getsampwidth()
                compression = recording.getcomptype()
                frames = recording.getnframes()
        except (OSError, EOFError, wave.Error) as exc:
            errors.append(f"Unreadable WAV {filename}: {exc}")
            continue
        details: list[str] = []
        if channels != VOICE_CHANNELS:
            details.append(f"{channels} channels")
        if sample_rate != VOICE_SAMPLE_RATE:
            details.append(f"{sample_rate} Hz")
        if sample_width != VOICE_SAMPLE_WIDTH:
            details.append(f"{sample_width * 8}-bit")
        if compression != VOICE_COMPRESSION:
            details.append(f"compression {compression}")
        if frames <= 0:
            details.append("no audio frames")
        if details:
            errors.append(f"Invalid WAV format {filename}: {', '.join(details)}")
        else:
            valid += 1
    return VoiceAssetReport(len(expected), valid, errors)
