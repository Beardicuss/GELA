import json
import threading

from voice_assistant import catalog_monitor
from voice_assistant.catalog import CatalogEntry
from voice_assistant.catalog_monitor import CatalogMonitor, set_auto_refresh_setting


def test_changed_catalog_signals_worker_reload(monkeypatch) -> None:
    reload_event = threading.Event()
    results = []
    entry = CatalogEntry("Steam", ["steam"], "app_id", "steam-id")
    monkeypatch.setattr(catalog_monitor, "scan_catalog_with_status", lambda: ([entry], True))
    monitor = CatalogMonitor(threading.Event(), reload_event, 300, callback=results.append)

    count, changed = monitor.refresh(invoke_callback=False)

    assert (count, changed) == (1, True)
    assert reload_event.is_set()
    assert results == []


def test_auto_refresh_setting_is_saved_atomically(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"catalog": {"auto_refresh": true}}', encoding="utf-8")

    set_auto_refresh_setting(False, settings_path)

    assert json.loads(settings_path.read_text(encoding="utf-8"))["catalog"]["auto_refresh"] is False
    assert not settings_path.with_suffix(".json.tmp").exists()
