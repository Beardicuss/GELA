from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import re
import time

from .catalog import CatalogEntry, executable_process_name
from .app_profiles import APP_PROFILES_PATH, AppProfile, profile_for
from .game_lifecycle import GAME_LIFECYCLE_PATH, record_game_observation
from .process_targets import (
    DEFAULT_PROCESS_TARGETS_PATH,
    LEARNED_PROCESS_TARGETS_PATH,
    process_targets_for,
    normalize_process_name,
    remember_process_target,
)


PROCESS_TARGETS_PATH = DEFAULT_PROCESS_TARGETS_PATH
LEARNED_TARGETS_PATH = LEARNED_PROCESS_TARGETS_PATH
GAME_STATE_PATH = GAME_LIFECYCLE_PATH
PROFILE_PATH = APP_PROFILES_PATH
APP_VERIFICATION_SECONDS = 12.0
GAME_VERIFICATION_SECONDS = 45.0
STABLE_EVIDENCE_SECONDS = 0.75


def launch(entry: CatalogEntry) -> None:
    if entry.launch_type == "app_id":
        os.startfile(f"shell:AppsFolder\\{entry.launch_value}")  # type: ignore[attr-defined]
        return
    if entry.launch_type == "uri":
        os.startfile(entry.launch_value)  # type: ignore[attr-defined]
        return
    raise ValueError(f"Unsupported launch type: {entry.launch_type}")


def _configured_process_names(entry: CatalogEntry, profile: AppProfile | None = None) -> set[str]:
    profile = profile or profile_for(entry.name, PROFILE_PATH)
    if profile.preferred_processes:
        return set(profile.preferred_processes)
    names = [
        *process_targets_for(entry.name, PROCESS_TARGETS_PATH, LEARNED_TARGETS_PATH),
        *entry.process_names,
    ]
    executable = executable_process_name(entry.launch_value)
    if executable:
        names.append(executable)
    return {normalized for name in names if (normalized := normalize_process_name(str(name)))}


def _running_process_names() -> set[str]:
    capacity = 4096
    while True:
        process_ids = (wintypes.DWORD * capacity)()
        returned = wintypes.DWORD()
        if not ctypes.windll.psapi.EnumProcesses(
            process_ids,
            ctypes.sizeof(process_ids),
            ctypes.byref(returned),
        ):
            raise OSError("Windows process enumeration failed")
        count = returned.value // ctypes.sizeof(wintypes.DWORD)
        if count < capacity:
            break
        capacity *= 2

    open_process = ctypes.windll.kernel32.OpenProcess
    open_process.restype = wintypes.HANDLE
    names: set[str] = set()
    for process_id in process_ids[:count]:
        handle = open_process(0x1000, False, process_id)
        if not handle:
            continue
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                buffer,
                ctypes.byref(size),
            ):
                names.add(Path(buffer.value).stem.casefold())
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    return names


def _window_process_name(hwnd: int) -> str | None:
    process_id = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if not process_id.value:
        return None
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id.value)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return None
        return Path(buffer.value).stem.casefold()
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _remember_verified_process(entry: CatalogEntry, process_name: str) -> None:
    if remember_process_target(
        entry.name,
        process_name,
        PROCESS_TARGETS_PATH,
        LEARNED_TARGETS_PATH,
    ):
        logging.info("Learned process target: app=%s process=%s", entry.name, process_name)


def _learn_new_window_owner(
    entry: CatalogEntry,
    hwnd: int,
    before_processes: set[str],
) -> str | None:
    process_name = _window_process_name(hwnd)
    if process_name and process_name not in before_processes:
        _remember_verified_process(entry, process_name)
        return process_name
    return None


def _visible_windows() -> dict[int, str]:
    windows: dict[int, str] = {}
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def callback(hwnd, _lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        if buffer.value.strip():
            windows[int(hwnd)] = buffer.value.strip()
        return True

    ctypes.windll.user32.EnumWindows(callback, 0)
    return windows


def _normalize_title(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _title_matches(
    entry: CatalogEntry,
    title: str,
    preferred_titles: list[str] | None = None,
) -> bool:
    normalized_title = _normalize_title(title)
    targets = {
        _normalize_title(entry.name),
        *(_normalize_title(alias) for alias in entry.aliases),
        *(_normalize_title(value) for value in (preferred_titles or [])),
    }
    return any(
        len(target) >= 3 and (target in normalized_title or normalized_title in target)
        for target in targets
        if target
    )


def launch_verified(
    entry: CatalogEntry,
    *,
    app_timeout: float = APP_VERIFICATION_SECONDS,
    game_timeout: float = GAME_VERIFICATION_SECONDS,
) -> str:
    profile = profile_for(entry.name, PROFILE_PATH)
    expected_processes = _configured_process_names(entry, profile)
    before_processes = _running_process_names()
    before_windows = _visible_windows()
    is_steam_game = entry.launch_value.casefold().startswith("steam://rungameid/")

    if expected_processes & before_processes:
        process = sorted(expected_processes & before_processes)[0]
        if is_steam_game:
            record_game_observation(
                entry.name,
                entry.launch_value,
                before_processes,
                before_processes,
                expected_processes,
                "running",
                verified_process=process,
                path=GAME_STATE_PATH,
            )
        return f"state already_running process={process}"
    existing_titles = [
        title
        for title in before_windows.values()
        if _title_matches(entry, title, profile.window_titles)
    ]
    if existing_titles:
        return f"state already_running window={existing_titles[0]}"

    launch(entry)

    timeout = game_timeout if is_steam_game else app_timeout
    deadline = time.monotonic() + timeout
    observed_process: str | None = None
    process_observed_at = 0.0
    observed_window: tuple[int, str] | None = None
    window_observed_at = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        running = _running_process_names()
        if is_steam_game:
            record_game_observation(
                entry.name,
                entry.launch_value,
                running,
                before_processes,
                expected_processes,
                "launching",
                path=GAME_STATE_PATH,
            )
        matched_processes = expected_processes & running
        if matched_processes:
            process = sorted(matched_processes)[0]
            if process != observed_process:
                observed_process = process
                process_observed_at = now
            elif now - process_observed_at >= STABLE_EVIDENCE_SECONDS:
                _remember_verified_process(entry, process)
                if is_steam_game:
                    record_game_observation(
                        entry.name,
                        entry.launch_value,
                        running,
                        before_processes,
                        expected_processes,
                        "running",
                        verified_process=process,
                        path=GAME_STATE_PATH,
                    )
                return f"verified stable process={process}"
        else:
            observed_process = None

        windows = _visible_windows()
        matching_titles = [
            (hwnd, title)
            for hwnd, title in windows.items()
            if _title_matches(entry, title, profile.window_titles)
        ]
        if matching_titles:
            window = matching_titles[0]
            if window != observed_window:
                observed_window = window
                window_observed_at = now
            elif now - window_observed_at >= STABLE_EVIDENCE_SECONDS:
                learned_process = _learn_new_window_owner(entry, window[0], before_processes)
                if is_steam_game and learned_process:
                    record_game_observation(
                        entry.name,
                        entry.launch_value,
                        running,
                        before_processes,
                        expected_processes | {learned_process},
                        "running",
                        verified_process=learned_process,
                        path=GAME_STATE_PATH,
                    )
                return f"verified stable window={window[1]}"
        else:
            observed_window = None

        if not expected_processes:
            changed_titles = [
                title
                for hwnd, title in windows.items()
                if hwnd not in before_windows or before_windows[hwnd] != title
            ]
            if changed_titles:
                window = next(
                    (item for item in windows.items() if item[1] == changed_titles[0]),
                    None,
                )
                if window is not None:
                    if window != observed_window:
                        observed_window = window
                        window_observed_at = now
                    elif now - window_observed_at >= STABLE_EVIDENCE_SECONDS:
                        return f"verified stable new window={window[1]}"
        time.sleep(0.25)

    if is_steam_game:
        record_game_observation(
            entry.name,
            entry.launch_value,
            _running_process_names(),
            before_processes,
            expected_processes,
            "failed",
            path=GAME_STATE_PATH,
        )
    expected = ", ".join(sorted(expected_processes)) or "a visible application window"
    raise RuntimeError(f"Launch was dispatched but not verified within {timeout:g}s; expected {expected}")
