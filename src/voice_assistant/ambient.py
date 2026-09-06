from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable


MOOD_ATTENTIVE = "ATTENTIVE"
MOOD_CALM = "CALM"
MOOD_SLEEPY = "SLEEPY"
MOOD_AWAY = "AWAY"


def mood_for_idle_seconds(idle_seconds: float) -> str:
    """Translate Windows input-idle time into a deliberately coarse mood."""
    if idle_seconds < 60:
        return MOOD_ATTENTIVE
    if idle_seconds < 5 * 60:
        return MOOD_CALM
    if idle_seconds < 7 * 60:
        return MOOD_SLEEPY
    return MOOD_AWAY


class _LastInputInfo(ctypes.Structure):
    _fields_ = (("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD))


def windows_idle_seconds() -> float:
    """Return time since the last keyboard, mouse, or touch input on Windows."""
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("GetLastInputInfo failed")
    # Both values are compared as 32-bit counters so the 49-day wrap is safe.
    current = int(kernel32.GetTickCount())
    elapsed_ms = (current - int(info.dwTime)) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


class AmbientMoodMonitor:
    def __init__(self, idle_supplier: Callable[[], float] = windows_idle_seconds) -> None:
        self._idle_supplier = idle_supplier
        self._last_mood = MOOD_ATTENTIVE

    def snapshot(self) -> str:
        try:
            self._last_mood = mood_for_idle_seconds(max(0.0, self._idle_supplier()))
        except (OSError, AttributeError):
            # A transient Windows API failure must never affect Gela or the board.
            pass
        return self._last_mood
