from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
import shutil
import socket
import threading
import time


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ac_line_status", ctypes.c_ubyte),
        ("battery_flag", ctypes.c_ubyte),
        ("battery_percent", ctypes.c_ubyte),
        ("system_status_flag", ctypes.c_ubyte),
        ("battery_life_time", ctypes.c_ulong),
        ("battery_full_life_time", ctypes.c_ulong),
    ]


def _filetime_value(value: ctypes.wintypes.FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


@dataclass
class _CpuTimes:
    idle: int
    total: int


class PcHealthMonitor:
    """Cached, dependency-free Windows health metrics for lightweight clients."""

    def __init__(self, cache_seconds: float = 2.0) -> None:
        self.cache_seconds = cache_seconds
        self._lock = threading.Lock()
        self._last_sample_at = 0.0
        self._last_cpu: _CpuTimes | None = None
        self._cached: dict[str, object] = {}

    def snapshot(self) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            if self._cached and now - self._last_sample_at < self.cache_seconds:
                return dict(self._cached)
            self._cached = self._sample()
            self._last_sample_at = now
            return dict(self._cached)

    def _sample_cpu(self) -> int | None:
        idle = ctypes.wintypes.FILETIME()
        kernel = ctypes.wintypes.FILETIME()
        user = ctypes.wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
        current = _CpuTimes(
            idle=_filetime_value(idle),
            total=_filetime_value(kernel) + _filetime_value(user),
        )
        previous, self._last_cpu = self._last_cpu, current
        if previous is None:
            return None
        total_delta = current.total - previous.total
        idle_delta = current.idle - previous.idle
        if total_delta <= 0:
            return None
        return max(0, min(100, round(100 * (total_delta - idle_delta) / total_delta)))

    def _sample(self) -> dict[str, object]:
        memory = _MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        memory_percent = None
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            memory_percent = int(memory.memory_load)

        disk = shutil.disk_usage("C:\\")
        disk_free_percent = round(100 * disk.free / disk.total) if disk.total else None

        power = _PowerStatus()
        battery_percent = None
        charging = False
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
            if power.battery_percent != 255:
                battery_percent = int(power.battery_percent)
            charging = power.ac_line_status == 1

        return {
            "cpuPercent": self._sample_cpu(),
            "memoryPercent": memory_percent,
            "diskFreePercent": disk_free_percent,
            "batteryPercent": battery_percent,
            "charging": charging,
            "network": "online" if _has_network_address() else "offline",
        }


def _has_network_address() -> bool:
    try:
        return any(
            address[4][0] not in {"127.0.0.1", "::1"}
            for address in socket.getaddrinfo(socket.gethostname(), None)
        )
    except OSError:
        return False
