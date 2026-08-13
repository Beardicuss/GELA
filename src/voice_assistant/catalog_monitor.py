from __future__ import annotations

import json
import logging
from pathlib import Path
import threading

from .catalog import scan_catalog_with_status
from .config import DEFAULT_CONFIG_PATH
from .storage import atomic_write_text


class CatalogMonitor:
    def __init__(
        self,
        stop_event: threading.Event,
        reload_event: threading.Event,
        interval_seconds: float,
        enabled: bool = True,
        refresh_on_start: bool = True,
        callback=None,
    ) -> None:
        self.stop_event = stop_event
        self.reload_event = reload_event
        self.interval_seconds = interval_seconds
        self.enabled_event = threading.Event()
        if enabled:
            self.enabled_event.set()
        self.refresh_on_start = refresh_on_start
        self.callback = callback
        self._scan_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.enabled_event.is_set()

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        if enabled:
            self.enabled_event.set()
        else:
            self.enabled_event.clear()
        if persist:
            set_auto_refresh_setting(enabled)

    def refresh(self, invoke_callback: bool = True) -> tuple[int, bool]:
        with self._scan_lock:
            entries, changed = scan_catalog_with_status()
        if changed:
            logging.info("Automatic catalog refresh detected %d launchable entries", len(entries))
            self.reload_event.set()
        if invoke_callback and self.callback is not None:
            self.callback(len(entries), changed)
        return len(entries), changed

    def run(self) -> None:
        if self.refresh_on_start and self.enabled:
            try:
                self.refresh()
            except Exception:
                logging.exception("Initial automatic catalog refresh failed")
        while not self.stop_event.wait(self.interval_seconds):
            if not self.enabled:
                continue
            try:
                self.refresh()
            except Exception:
                logging.exception("Automatic catalog refresh failed")


def set_auto_refresh_setting(enabled: bool, path: Path = DEFAULT_CONFIG_PATH) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["catalog"]["auto_refresh"] = enabled
    atomic_write_text(path, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
