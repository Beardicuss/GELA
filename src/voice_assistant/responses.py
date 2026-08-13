from __future__ import annotations

import json
from pathlib import Path
import threading
import wave
import winsound

from .config import PROJECT_ROOT


RESPONSES_CONFIG = PROJECT_ROOT / "config" / "voice_responses.json"


def response_event_for_detail(detail: str | None) -> str:
    if not detail:
        return "launch_success"
    state_events = {
        "state already_running": "already_running",
        "state already_stopped": "already_stopped",
        "state already_on": "already_on",
        "state already_off": "already_off",
    }
    return next(
        (event for prefix, event in state_events.items() if detail.startswith(prefix)),
        "launch_success",
    )


class VoiceResponses:
    _playback_stop = threading.Event()
    _playback_lock = threading.Lock()

    def __init__(self, config_path: Path = RESPONSES_CONFIG) -> None:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        self.enabled = bool(raw.get("enabled", True))
        self.paths = {
            event: (PROJECT_ROOT / relative_path).resolve()
            for event, relative_path in raw.get("responses", {}).items()
        }

    def play(self, event: str, fallback: int = winsound.MB_OK) -> bool:
        path = self.paths.get(event)
        if self.enabled and path is not None and path.is_file():
            with self._playback_lock:
                self._playback_stop.clear()
                with wave.open(str(path), "rb") as recording:
                    duration = recording.getnframes() / recording.getframerate()
                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC,
                )
                self._playback_stop.wait(duration + 0.1)
                winsound.PlaySound(None, 0)
            return True
        winsound.MessageBeep(fallback)
        return False

    def available(self, event: str) -> bool:
        path = self.paths.get(event)
        return bool(self.enabled and path is not None and path.is_file())

    @staticmethod
    def stop() -> None:
        """Immediately stop the response currently playing through Windows."""
        VoiceResponses._playback_stop.set()
        winsound.PlaySound(None, 0)

    def coverage(self) -> dict[str, list[str]]:
        missing = [event for event, path in self.paths.items() if not path.is_file()]
        expected = {path.resolve() for path in self.paths.values()}
        processed = PROJECT_ROOT / "audio" / "voice" / "processed"
        orphaned = [
            str(path.relative_to(PROJECT_ROOT))
            for path in processed.glob("*.wav")
            if path.resolve() not in expected
        ]
        return {"missing": missing, "orphaned": sorted(orphaned)}
