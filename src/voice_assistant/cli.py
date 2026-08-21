from __future__ import annotations

import argparse
from pathlib import Path

from .audio import find_input_device, input_devices, verify_input_stream
from .catalog import alias_index, load_catalog, normalize_phrase, scan_catalog
from .config import PROJECT_ROOT, load_settings
from .launcher import launch
from .models import validate_model_directory
from .recognizer import listen_for_app
from .startup import install_startup, startup_shortcut, uninstall_startup
from .vocabulary import AUDIT_PATH, audit_georgian
from .responses import VoiceResponses
from .audio_test import recognize_command_file
from .voice_assets import validate_processed_voice_assets


def list_microphones() -> int:
    devices = input_devices()
    if not devices:
        print("No microphone input devices found.")
        return 1
    for index, device in devices:
        marker = " (default input)" if index == __import__("sounddevice").default.device[0] else ""
        print(f"{index}: {device['name']} | inputs={device['max_input_channels']} | default_rate={device['default_samplerate']:g}{marker}")
    return 0


def doctor() -> int:
    settings = load_settings()
    print("Configuration: OK")

    index, device = find_input_device(settings.audio.device_name_contains)
    peak = verify_input_stream(index, settings.audio.sample_rate, settings.audio.channels)
    print(f"Microphone: OK ({index}: {device['name']})")
    print(f"Audio capture: OK ({settings.audio.sample_rate} Hz, mono, int16; sample peak={peak})")

    failed = False
    for language, path in settings.models.items():
        try:
            validate_model_directory(path)
            print(f"Vosk model {language}: OK ({path.name})")
        except (FileNotFoundError, RuntimeError) as exc:
            failed = True
            print(f"Vosk model {language}: MISSING/INVALID ({exc})")
    return 1 if failed else 0


def find_app(query: str):
    entries = load_catalog()
    normalized = normalize_phrase(query)
    exact = alias_index(entries).get(normalized)
    if exact:
        return exact
    matches = [entry for entry in entries if normalized in normalize_phrase(entry.name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"No catalog app matches {query!r}")
    names = ", ".join(entry.name for entry in matches[:12])
    raise RuntimeError(f"App name is ambiguous ({len(matches)} matches): {names}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple offline voice assistant tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list-mics")
    subparsers.add_parser("doctor")
    subparsers.add_parser("scan-apps")
    apps_parser = subparsers.add_parser("apps")
    apps_parser.add_argument("search", nargs="?", default="")
    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("name")
    listen_parser = subparsers.add_parser("listen")
    listen_parser.add_argument("--language", choices=("en", "ka"), default="en")
    listen_parser.add_argument("--seconds", type=float, default=6.0)
    subparsers.add_parser("install-startup")
    subparsers.add_parser("uninstall-startup")
    subparsers.add_parser("startup-status")
    subparsers.add_parser("audit-vocabulary")
    subparsers.add_parser("voice-status")
    bridge_parser = subparsers.add_parser("mobile-bridge")
    bridge_parser.add_argument("--port", type=int, default=8765)
    test_voice_parser = subparsers.add_parser("test-voice")
    test_voice_parser.add_argument("event")
    audio_test_parser = subparsers.add_parser("test-command-audio")
    audio_test_parser.add_argument("path")
    audio_test_parser.add_argument("--language", choices=("ka", "en"), default="ka")
    args = parser.parse_args()
    if args.command == "list-mics":
        return list_microphones()
    if args.command == "doctor":
        return doctor()
    if args.command == "scan-apps":
        entries = scan_catalog()
        print(f"Catalog saved with {len(entries)} launchable entries.")
        return 0
    if args.command == "apps":
        query = normalize_phrase(args.search)
        entries = [entry for entry in load_catalog() if query in normalize_phrase(entry.name)]
        for entry in entries:
            print(entry.name)
        print(f"{len(entries)} matching entries")
        return 0
    if args.command == "open":
        entry = find_app(args.name)
        launch(entry)
        print(f"Opened: {entry.name}")
        return 0
    if args.command == "listen":
        entries = load_catalog()
        print(f"Listening for up to {args.seconds:g} seconds ({args.language})...")
        text, entry = listen_for_app(entries, load_settings(), args.language, args.seconds)
        print(f"Recognized: {text or '[nothing]'}")
        if entry is None:
            print("No catalog command matched.")
            return 1
        launch(entry)
        print(f"Opened: {entry.name}")
        return 0
    if args.command == "install-startup":
        path = install_startup()
        print(f"Startup enabled: {path}")
        return 0
    if args.command == "uninstall-startup":
        print("Startup disabled." if uninstall_startup() else "Startup was not enabled.")
        return 0
    if args.command == "startup-status":
        path = startup_shortcut()
        print(f"Startup: {'enabled' if path.is_file() else 'disabled'} ({path})")
        return 0
    if args.command == "audit-vocabulary":
        report = audit_georgian()
        print(f"Catalog entries: {report['catalog_entries']}")
        print(f"With valid Georgian aliases: {report['covered_entries']}")
        print(f"Without valid Georgian aliases: {report['uncovered_entries']}")
        print(f"Rejected Georgian words: {', '.join(report['missing_words']) or 'none'}")
        print(f"Detailed report: {AUDIT_PATH}")
        return 0
    if args.command == "voice-status":
        coverage = VoiceResponses().coverage()
        assets = validate_processed_voice_assets(
            PROJECT_ROOT / "audio" / "voice" / "recording_manifest.csv",
            PROJECT_ROOT / "audio" / "voice" / "processed",
        )
        print(f"Missing recordings: {', '.join(coverage['missing']) or 'none'}")
        print(f"Orphaned recordings: {', '.join(coverage['orphaned']) or 'none'}")
        print(f"Invalid recordings: {', '.join(assets.errors) or 'none'}")
        return 1 if coverage["missing"] or assets.errors else 0
    if args.command == "mobile-bridge":
        from .mobile_bridge import serve_mobile_bridge

        serve_mobile_bridge(port=args.port)
        return 0
    if args.command == "test-voice":
        played = VoiceResponses().play(args.event)
        print("Played recorded response." if played else "Recording missing; played fallback beep.")
        return 0 if played else 1
    if args.command == "test-command-audio":
        result, app = recognize_command_file(Path(args.path), args.language)
        print(f"Recognized: {result.text or '[nothing]'}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Catalog match: {app or 'none'}")
        return 0 if app else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
