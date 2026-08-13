import csv
import wave

from voice_assistant.voice_assets import validate_processed_voice_assets


def _manifest(path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("event", "processed_filename"))
        writer.writeheader()
        writer.writerows(rows)


def _wav(path, *, rate: int = 48_000, channels: int = 1, width: int = 2) -> None:
    with wave.open(str(path), "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(width)
        recording.setframerate(rate)
        recording.writeframes(b"\x00" * width * channels * 480)


def test_voice_asset_validation_accepts_release_format(tmp_path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, [{"event": "ready", "processed_filename": "ready.wav"}])
    _wav(processed / "ready.wav")

    report = validate_processed_voice_assets(manifest, processed)

    assert report.expected_files == 1
    assert report.valid_files == 1
    assert report.errors == []


def test_voice_asset_validation_reports_format_and_inventory_errors(tmp_path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    manifest = tmp_path / "manifest.csv"
    _manifest(
        manifest,
        [
            {"event": "ready", "processed_filename": "ready.wav"},
            {"event": "failed", "processed_filename": "missing.wav"},
        ],
    )
    _wav(processed / "ready.wav", rate=24_000)
    _wav(processed / "orphan.wav")

    report = validate_processed_voice_assets(manifest, processed)

    assert report.valid_files == 0
    assert "Missing processed response: missing.wav" in report.errors
    assert "Orphaned processed response: orphan.wav" in report.errors
    assert "Invalid WAV format ready.wav: 24000 Hz" in report.errors
