from __future__ import annotations

from pathlib import Path

from voice_assistant.voice_assets import validate_processed_voice_assets


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = validate_processed_voice_assets(
        root / "audio" / "voice" / "recording_manifest.csv",
        root / "audio" / "voice" / "processed",
    )
    for error in report.errors:
        print(f"ERROR: {error}")
    if report.errors:
        print(f"Voice assets: {report.valid_files}/{report.expected_files} valid")
        return 1
    print(
        f"Voice assets: {report.valid_files}/{report.expected_files} valid "
        "(48 kHz, mono, 16-bit PCM)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
