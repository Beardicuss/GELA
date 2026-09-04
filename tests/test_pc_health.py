from __future__ import annotations

import time

from voice_assistant.pc_health import PcHealthMonitor


def test_pc_health_snapshot_has_bounded_windows_metrics():
    monitor = PcHealthMonitor(cache_seconds=0)
    first = monitor.snapshot()
    time.sleep(0.02)
    second = monitor.snapshot()

    assert first["network"] in {"online", "offline"}
    for name in ("memoryPercent", "diskFreePercent", "batteryPercent"):
        value = second[name]
        assert value is None or 0 <= value <= 100
    assert second["cpuPercent"] is None or 0 <= second["cpuPercent"] <= 100
    assert isinstance(second["charging"], bool)


def test_pc_health_snapshot_is_returned_as_a_copy():
    monitor = PcHealthMonitor(cache_seconds=60)
    first = monitor.snapshot()
    first["network"] = "changed"
    assert monitor.snapshot()["network"] != "changed"
