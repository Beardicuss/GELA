from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time

from PIL import ImageGrab

from .catalog import CatalogEntry, executable_process_name, normalize_phrase
from .app_profiles import APP_PROFILES_PATH, profile_for
from .game_lifecycle import (
    GAME_LIFECYCLE_PATH,
    gameplay_processes_for,
    is_gameplay_process,
    mark_game_stopped,
)
from .process_targets import (
    DEFAULT_PROCESS_TARGETS_PATH,
    LEARNED_PROCESS_TARGETS_PATH,
    learned_process_targets_for,
    load_process_targets,
    normalize_process_name,
)
from .windows_process import hidden_process_kwargs


PROCESS_TARGETS_PATH = DEFAULT_PROCESS_TARGETS_PATH
LEARNED_TARGETS_PATH = LEARNED_PROCESS_TARGETS_PATH
GAME_STATE_PATH = GAME_LIFECYCLE_PATH
PROFILE_PATH = APP_PROFILES_PATH


@dataclass(frozen=True)
class SystemAction:
    name: str
    action_id: str
    value: str = ""


STATIC_ACTIONS = {
    "ka": {
        "გახსენი ჩამოტვირთვები": SystemAction("Open Downloads", "open_shell", "Downloads"),
        "გახსენი დოკუმენტები": SystemAction("Open Documents", "open_shell", "Personal"),
        "გახსენი სურათები": SystemAction("Open Pictures", "open_shell", "My Pictures"),
        "გახსენი დესკტოპი": SystemAction("Open Desktop", "open_shell", "Desktop"),
        "გახსენი მუსიკა": SystemAction("Open Music", "open_shell", "My Music"),
        "გახსენი ვიდეო": SystemAction("Open Videos", "open_shell", "My Video"),
        "გახსენი ნაგვის კალათა": SystemAction("Open Recycle Bin", "open_shell", "RecycleBinFolder"),
        "ხმა აუწიე": SystemAction("Volume Up", "volume_up"),
        "ხმას აუწიე": SystemAction("Volume Up", "volume_up"),
        "ხმა დაუწიე": SystemAction("Volume Down", "volume_down"),
        "ხმას დაუწიე": SystemAction("Volume Down", "volume_down"),
        "ხმა გამორთე": SystemAction("Toggle Mute", "volume_mute"),
        "ხმა გათიშე": SystemAction("Toggle Mute", "volume_mute"),
        "ხმა ჩართე": SystemAction("Toggle Mute", "volume_mute"),
        "გადაიღე ეკრანი": SystemAction("Take Screenshot", "screenshot"),
        "ჩაკეტე კომპიუტერი": SystemAction("Lock Windows", "lock_windows"),
        "გამორთე კომპიუტერი": SystemAction("Shut down computer", "power_shutdown"),
        "დაარესტარტე კომპიუტერი": SystemAction("Restart computer", "power_restart"),
        "დააძინე კომპიუტერი": SystemAction("Put computer to sleep", "power_sleep"),
        "დამალე ფანჯარა": SystemAction("Minimize active window", "window_active", "minimize"),
        "ჩაკეცე": SystemAction("Minimize active window", "window_active", "minimize"),
        "ჩაკეცე ფანჯარა": SystemAction("Minimize active window", "window_active", "minimize"),
        "გაზარდე ფანჯარა": SystemAction("Maximize active window", "window_active", "maximize"),
        "გაადიდე": SystemAction("Maximize active window", "window_active", "maximize"),
        "გაადიდე ფანჯარა": SystemAction("Maximize active window", "window_active", "maximize"),
        "აღადგინე ფანჯარა": SystemAction("Restore active window", "window_active", "restore"),
        "ამოკეცე": SystemAction("Restore active window", "window_active", "restore"),
        "ამოკეცე ფანჯარა": SystemAction("Restore active window", "window_active", "restore"),
        "დააპატარავე": SystemAction("Restore active window", "window_active", "restore"),
        "დააპატარავე ფანჯარა": SystemAction("Restore active window", "window_active", "restore"),
        "აჩვენე დესკტოპი": SystemAction("Show desktop", "hotkey", "win+d"),
        "გახსენი სწრაფი პარამეტრები": SystemAction("Open Quick Settings", "hotkey", "win+a"),
        "აჩვენე შეტყობინებები": SystemAction("Open notifications", "hotkey", "win+n"),
        "აჩვენე ყველა ფანჯარა": SystemAction("Open Task View", "hotkey", "win+tab"),
        "გახსენი პარამეტრები": SystemAction("Open Windows Settings", "open_uri", "ms-settings:"),
        "გახსენი ვაიფაი": SystemAction("Open Wi-Fi settings", "open_uri", "ms-settings:network-wifi"),
        "გახსენი ბლუთუზი": SystemAction("Open Bluetooth settings", "open_uri", "ms-settings:bluetooth"),
        "ჩართე ვაიფაი": SystemAction("Turn on Wi-Fi", "radio", "WiFi:on"),
        "ჩართე ვაი ფაი": SystemAction("Turn on Wi-Fi", "radio", "WiFi:on"),
        "გამორთე ვაიფაი": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "გამორთე ვაი ფაი": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "გათიშე ვაიფაი": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "გათიშე ვაი ფაი": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "ჩართე ბლუთუზი": SystemAction("Turn on Bluetooth", "radio", "Bluetooth:on"),
        "ჩართე ბლუთუსი": SystemAction("Turn on Bluetooth", "radio", "Bluetooth:on"),
        "გამორთე ბლუთუზი": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "გამორთე ბლუთუსი": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "გათიშე ბლუთუზი": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "გათიშე ბლუთუსი": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "ჩართე ფრენის რეჟიმი": SystemAction("Turn on flight mode", "airplane_mode", "on"),
        "გამორთე ფრენის რეჟიმი": SystemAction("Turn off flight mode", "airplane_mode", "off"),
        "გახსენი ეკრანის პარამეტრები": SystemAction("Open Display settings", "open_uri", "ms-settings:display"),
        "გახსენი ხმის პარამეტრები": SystemAction("Open Sound settings", "open_uri", "ms-settings:sound"),
        "გახსენი განახლებები": SystemAction("Open Windows Update", "open_uri", "ms-settings:windowsupdate"),
        "სიკაშკაშე გაზარდე": SystemAction("Increase brightness", "brightness", "10"),
        "სიკაშკაშე შეამცირე": SystemAction("Decrease brightness", "brightness", "-10"),
        "დაუკარი მუსიკა": SystemAction("Play or pause media", "media_key", "play_pause"),
        "შეაჩერე მუსიკა": SystemAction("Pause media", "media_key", "play_pause"),
        "გააგრძელე მუსიკა": SystemAction("Resume media", "media_key", "play_pause"),
        "გააჩერე მუსიკა": SystemAction("Stop media", "media_key", "stop"),
        "შემდეგი სიმღერა": SystemAction("Next track", "media_key", "next"),
        "წინა სიმღერა": SystemAction("Previous track", "media_key", "previous"),
    },
    "en": {
        "open downloads": SystemAction("Open Downloads", "open_shell", "Downloads"),
        "open documents": SystemAction("Open Documents", "open_shell", "Personal"),
        "open pictures": SystemAction("Open Pictures", "open_shell", "My Pictures"),
        "open desktop": SystemAction("Open Desktop", "open_shell", "Desktop"),
        "open music": SystemAction("Open Music", "open_shell", "My Music"),
        "open videos": SystemAction("Open Videos", "open_shell", "My Video"),
        "open recycle bin": SystemAction("Open Recycle Bin", "open_shell", "RecycleBinFolder"),
        "volume up": SystemAction("Volume Up", "volume_up"),
        "volume down": SystemAction("Volume Down", "volume_down"),
        "mute volume": SystemAction("Toggle Mute", "volume_mute"),
        "take screenshot": SystemAction("Take Screenshot", "screenshot"),
        "lock computer": SystemAction("Lock Windows", "lock_windows"),
        "minimize window": SystemAction("Minimize active window", "window_active", "minimize"),
        "maximize window": SystemAction("Maximize active window", "window_active", "maximize"),
        "restore window": SystemAction("Restore active window", "window_active", "restore"),
        "show desktop": SystemAction("Show desktop", "hotkey", "win+d"),
        "open quick settings": SystemAction("Open Quick Settings", "hotkey", "win+a"),
        "show notifications": SystemAction("Open notifications", "hotkey", "win+n"),
        "show all windows": SystemAction("Open Task View", "hotkey", "win+tab"),
        "open settings": SystemAction("Open Windows Settings", "open_uri", "ms-settings:"),
        "open wifi settings": SystemAction("Open Wi-Fi settings", "open_uri", "ms-settings:network-wifi"),
        "open bluetooth settings": SystemAction("Open Bluetooth settings", "open_uri", "ms-settings:bluetooth"),
        "turn on wifi": SystemAction("Turn on Wi-Fi", "radio", "WiFi:on"),
        "enable wifi": SystemAction("Turn on Wi-Fi", "radio", "WiFi:on"),
        "turn off wifi": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "disable wifi": SystemAction("Turn off Wi-Fi", "radio", "WiFi:off"),
        "turn on bluetooth": SystemAction("Turn on Bluetooth", "radio", "Bluetooth:on"),
        "enable bluetooth": SystemAction("Turn on Bluetooth", "radio", "Bluetooth:on"),
        "turn off bluetooth": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "disable bluetooth": SystemAction("Turn off Bluetooth", "radio", "Bluetooth:off"),
        "open display settings": SystemAction("Open Display settings", "open_uri", "ms-settings:display"),
        "open sound settings": SystemAction("Open Sound settings", "open_uri", "ms-settings:sound"),
        "open windows update": SystemAction("Open Windows Update", "open_uri", "ms-settings:windowsupdate"),
        "increase brightness": SystemAction("Increase brightness", "brightness", "10"),
        "decrease brightness": SystemAction("Decrease brightness", "brightness", "-10"),
        "play music": SystemAction("Play or pause media", "media_key", "play_pause"),
        "pause music": SystemAction("Pause media", "media_key", "play_pause"),
        "resume music": SystemAction("Resume media", "media_key", "play_pause"),
        "stop media": SystemAction("Stop media", "media_key", "stop"),
        "next track": SystemAction("Next track", "media_key", "next"),
        "previous track": SystemAction("Previous track", "media_key", "previous"),
    },
}


def build_action_phrases(
    entries: list[CatalogEntry], language: str, english_aliases: dict[str, list[str]] | None = None
) -> dict[str, SystemAction]:
    phrases = dict(STATIC_ACTIONS[language])
    process_targets = load_process_targets(PROCESS_TARGETS_PATH, LEARNED_TARGETS_PATH)
    entries_by_name = {entry.name: entry for entry in entries}
    close_prefixes = ("დახურე", "გამორთე", "გათიშე") if language == "ka" else ("close", "exit", "quit")
    window_prefixes = (
        {
            "window_focus": ("გადადი", "მაჩვენე"),
            "window_minimize": ("დამალე", "ჩაკეცე"),
            "window_maximize": ("გაზარდე", "გაადიდე"),
            "window_restore": ("აღადგინე", "ამოკეცე", "დააპატარავე"),
        }
        if language == "ka"
        else {
            "window_focus": ("switch to", "focus"),
            "window_minimize": ("minimize",),
            "window_maximize": ("maximize",),
            "window_restore": ("restore",),
        }
    )
    for entry in entries:
        app_name = entry.name
        profile = profile_for(app_name, PROFILE_PATH)
        if profile.preferred_processes:
            process_names = list(profile.preferred_processes)
        else:
            process_names = list(process_targets.get(app_name, []))
            process_names.extend(name for name in entry.process_names if name not in process_names)
            process_names.extend(name for name in _infer_process_names(entry) if name not in process_names)
        aliases = (
            entry.aliases
            if language == "ka"
            else (english_aliases or {}).get(app_name, [normalize_phrase(app_name)])
        )
        target = {"name": app_name, "processes": process_names}
        if entry.launch_value.casefold().startswith("steam://rungameid/"):
            target["kind"] = "steam_game"
        close_value = json.dumps(
            target,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        close_action = SystemAction(app_name, "close_app", close_value)
        window_value = close_value
        for alias in aliases:
            normalized_alias = normalize_phrase(alias)
            for prefix in close_prefixes:
                phrases[f"{prefix} {normalized_alias}"] = close_action
            for action_id, prefixes in window_prefixes.items():
                action = SystemAction(app_name, action_id, window_value)
                for prefix in prefixes:
                    phrases[f"{prefix} {normalized_alias}"] = action
    return phrases


def _infer_process_names(entry: CatalogEntry) -> list[str]:
    name = executable_process_name(entry.launch_value)
    return [name] if name else []


def _press_media_key(key_code: int, presses: int = 1) -> None:
    for _ in range(presses):
        ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)


def _control_media(value: str) -> None:
    media_keys = {
        "next": 0xB0,
        "previous": 0xB1,
        "stop": 0xB2,
        "play_pause": 0xB3,
    }
    key_code = media_keys.get(value)
    if key_code is None:
        raise ValueError("Unknown fixed media control")
    _press_media_key(key_code)


def _press_hotkey(value: str) -> None:
    key_codes = {
        "win": 0x5B,
        "a": 0x41,
        "d": 0x44,
        "n": 0x4E,
        "tab": 0x09,
    }
    names = value.split("+")
    if not names or any(name not in key_codes for name in names):
        raise ValueError("Unknown fixed hotkey")
    codes = [key_codes[name] for name in names]
    for code in codes:
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)


def _adjust_brightness(delta: int) -> int:
    if delta not in {-10, 10}:
        raise ValueError("Brightness adjustment must be exactly 10 percent")
    script = (
        "$b=Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction SilentlyContinue|"
        "Select-Object -First 1;"
        "$m=Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue|"
        "Select-Object -First 1;"
        "if($null-eq $b-or $null-eq $m){exit 3};"
        f"$n=[Math]::Max(0,[Math]::Min(100,[int]$b.CurrentBrightness+({delta})));"
        "$null=Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
        "-Arguments @{Timeout=1;Brightness=[byte]$n};Write-Output $n"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        **hidden_process_kwargs(),
    )
    if result.returncode == 3:
        raise RuntimeError("This monitor does not expose Windows brightness control")
    if result.returncode != 0:
        raise RuntimeError("Windows brightness adjustment failed")
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Windows did not report the new brightness") from exc


def _set_radio(value: str) -> str:
    allowed = {
        "WiFi:on": ("WiFi", "On"),
        "WiFi:off": ("WiFi", "Off"),
        "Bluetooth:on": ("Bluetooth", "On"),
        "Bluetooth:off": ("Bluetooth", "Off"),
    }
    selection = allowed.get(value)
    if selection is None:
        raise ValueError("Unknown fixed radio control")
    kind, requested_state = selection
    script = f"""
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]
$null=[Windows.Devices.Radios.RadioKind,Windows.System.Devices,ContentType=WindowsRuntime]
$null=[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime]
$null=[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]
$asTaskGeneric=([System.WindowsRuntimeSystemExtensions].GetMethods()|Where-Object{{$_.Name-eq'AsTask'-and $_.IsGenericMethod-and $_.GetParameters().Count-eq 1}})[0]
function Await($operation,$resultType){{$method=$asTaskGeneric.MakeGenericMethod($resultType);$task=$method.Invoke($null,@($operation));$task.Wait();$task.Result}}
$access=Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
if($access-ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed){{Write-Output "access=$access";exit 3}}
$listType=[System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]
$radios=Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) $listType
$radio=$radios|Where-Object{{$_.Kind-eq [Windows.Devices.Radios.RadioKind]::{kind}}}|Select-Object -First 1
if($null-eq $radio){{exit 4}}
$target=[Windows.Devices.Radios.RadioState]::{requested_state}
if($radio.State-eq $target){{Write-Output "already={kind}:{requested_state}";exit 0}}
$result=Await ($radio.SetStateAsync($target)) ([Windows.Devices.Radios.RadioAccessStatus])
if($result-ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed){{Write-Output "result=$result";exit 5}}
for($attempt=0;$attempt-lt 20-and $radio.State-ne $target;$attempt++){{Start-Sleep -Milliseconds 250}}
if($radio.State-ne $target){{Write-Output "state=$($radio.State)";exit 6}}
Write-Output "{kind}=$($radio.State)"
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        **hidden_process_kwargs(),
    )
    if result.returncode == 3:
        raise RuntimeError("Windows denied access to radio controls")
    if result.returncode == 4:
        raise RuntimeError(f"{kind} radio was not found")
    if result.returncode == 5:
        raise RuntimeError(f"Windows refused to change {kind}")
    if result.returncode == 6:
        raise RuntimeError(f"{kind} did not reach the requested state")
    if result.returncode != 0:
        raise RuntimeError(f"Windows {kind} control failed")
    output = result.stdout.strip()
    if output == f"already={kind}:{requested_state}":
        state = "already_on" if requested_state == "On" else "already_off"
        return f"state {state} radio={kind}"
    return output


def _set_airplane_mode(value: str) -> str:
    """Apply Gela's flight mode to the PC's Wi-Fi and Bluetooth radios."""
    if value not in {"on", "off"}:
        raise ValueError("Unknown fixed flight-mode control")
    requested_radio_state = "off" if value == "on" else "on"
    results = [
        _set_radio(f"WiFi:{requested_radio_state}"),
        _set_radio(f"Bluetooth:{requested_radio_state}"),
    ]
    already_marker = "already_off" if value == "on" else "already_on"
    if all(already_marker in result for result in results):
        mode_state = "already_on" if value == "on" else "already_off"
        return f"state {mode_state} flight_mode"
    return f"flight_mode={value}"


def _close_process_windows(value: str, allow_force: bool = True) -> None:
    names = value.split("|")
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in names):
        raise ValueError("Invalid allowlisted process name")
    quoted = ",".join("'" + name.replace("'", "''") + "'" for name in names)
    script = (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public static class GelaNativeWindow{[DllImport(\"user32.dll\")]"
        "public static extern bool IsWindowVisible(IntPtr hWnd);}';"
        f"$p=Get-Process -Name @({quoted}) -ErrorAction SilentlyContinue;"
        "if(-not $p){exit 3};"
        "foreach($item in $p){$null=$item.CloseMainWindow()};"
        "$deadline=(Get-Date).AddSeconds(5);do{Start-Sleep -Milliseconds 250;"
        f"$remaining=Get-Process -Name @({quoted}) -ErrorAction SilentlyContinue"
        "}while($remaining-and(Get-Date)-lt $deadline);"
        "if(-not $remaining){exit 0};"
        "$visible=$false;foreach($item in $remaining){if($item.MainWindowHandle-ne 0-and"
        "[GelaNativeWindow]::IsWindowVisible($item.MainWindowHandle)){$visible=$true}};"
        "if($visible){exit 4};"
    )
    if allow_force:
        script += (
            "$remaining|Stop-Process -Force -ErrorAction Stop;Start-Sleep -Milliseconds 300;"
            f"if(Get-Process -Name @({quoted}) -ErrorAction SilentlyContinue){{exit 5}}"
        )
    else:
        script += "exit 6"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        **hidden_process_kwargs(),
    )
    if result.returncode == 3:
        raise RuntimeError("Application is not running")
    if result.returncode == 4:
        raise RuntimeError("Application is waiting for confirmation or unsaved work")
    if result.returncode == 6:
        raise RuntimeError("Application remains running in the background")
    if result.returncode != 0:
        raise RuntimeError("Application could not be closed completely")


def _matching_title_windows(app_name: str) -> list[int]:
    target = normalize_phrase(app_name)
    if len(target) < 3:
        return []
    matches: list[int] = []
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
        title = normalize_phrase(buffer.value)
        if target in title or (len(title) >= 4 and title in target):
            matches.append(int(hwnd))
        return True

    ctypes.windll.user32.EnumWindows(callback, 0)
    return matches


def _matching_profile_title_windows(app_name: str, window_titles: list[str]) -> list[int]:
    matches: list[int] = []
    for title in [app_name, *window_titles]:
        matches.extend(hwnd for hwnd in _matching_title_windows(title) if hwnd not in matches)
    return matches


def _close_title_windows(app_name: str, window_titles: list[str] | None = None) -> None:
    windows = (
        _matching_profile_title_windows(app_name, window_titles)
        if window_titles
        else _matching_title_windows(app_name)
    )
    if not windows:
        raise RuntimeError("Application is not running or its window could not be identified")
    for hwnd in windows:
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not any(
            ctypes.windll.user32.IsWindow(hwnd)
            and ctypes.windll.user32.IsWindowVisible(hwnd)
            for hwnd in windows
        ):
            return
        time.sleep(0.25)
    raise RuntimeError("Application is waiting for confirmation or unsaved work")


def _close_profile_title_windows(app_name: str, window_titles: list[str]) -> None:
    if window_titles:
        _close_title_windows(app_name, window_titles)
    else:
        _close_title_windows(app_name)


def _close_catalog_app(value: str) -> str:
    try:
        target = json.loads(value)
        app_name = str(target["name"])
        process_names = target.get("processes", [])
        target_kind = target.get("kind", "application")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Invalid catalog close target") from exc
    if not isinstance(process_names, list):
        raise ValueError("Invalid catalog process list")
    profile = profile_for(app_name, PROFILE_PATH)
    if profile.preferred_processes:
        valid_names = list(profile.preferred_processes)
    else:
        valid_names = [str(name) for name in process_names]
        known_names = {normalized for name in valid_names if (normalized := normalize_process_name(name))}
        valid_names.extend(
            name
            for name in learned_process_targets_for(app_name, LEARNED_TARGETS_PATH)
            if normalize_process_name(name) not in known_names
        )
    if target_kind == "steam_game":
        valid_names.extend(
            name
            for name in gameplay_processes_for(app_name, GAME_STATE_PATH)
            if name not in valid_names
        )
        valid_names = [name for name in valid_names if is_gameplay_process(name)]
    elif target_kind != "application":
        raise ValueError("Invalid catalog target kind")
    if profile.close_behavior == "window_only":
        try:
            _close_profile_title_windows(app_name, profile.window_titles)
        except RuntimeError as exc:
            if "not running" in str(exc):
                if target_kind == "steam_game":
                    mark_game_stopped(app_name, GAME_STATE_PATH)
                return f"state already_stopped app={app_name}"
            raise
        if target_kind == "steam_game":
            mark_game_stopped(app_name, GAME_STATE_PATH)
        return f"verified window closed={app_name}"
    if not valid_names:
        valid_names.extend(
            _matching_title_process_names(app_name, profile.window_titles)
            if profile.window_titles
            else _matching_title_process_names(app_name)
        )
    if valid_names:
        try:
            if profile.close_behavior == "graceful_only":
                _close_process_windows("|".join(valid_names), allow_force=False)
            else:
                _close_process_windows("|".join(valid_names))
            if target_kind == "steam_game":
                mark_game_stopped(app_name, GAME_STATE_PATH)
            return f"verified processes exited={','.join(valid_names)}"
        except RuntimeError as process_error:
            # Packaged apps may expose their visible window through a host
            # process that ignores Process.CloseMainWindow(). Try the same
            # normal WM_CLOSE request through the catalog title before
            # reporting the original process-level failure.
            try:
                _close_profile_title_windows(app_name, profile.window_titles)
            except RuntimeError as title_error:
                if "not running" in str(process_error) and "not running" in str(title_error):
                    if target_kind == "steam_game":
                        mark_game_stopped(app_name, GAME_STATE_PATH)
                    return f"state already_stopped app={app_name}"
                if "not running" not in str(process_error):
                    raise process_error
            else:
                try:
                    if profile.close_behavior == "graceful_only":
                        _close_process_windows("|".join(valid_names), allow_force=False)
                    else:
                        _close_process_windows("|".join(valid_names))
                except RuntimeError as final_error:
                    if "not running" not in str(final_error):
                        raise
                if target_kind == "steam_game":
                    mark_game_stopped(app_name, GAME_STATE_PATH)
                return f"verified processes exited={','.join(valid_names)}"
    try:
        _close_profile_title_windows(app_name, profile.window_titles)
    except RuntimeError as exc:
        if "not running" in str(exc):
            if target_kind == "steam_game":
                mark_game_stopped(app_name, GAME_STATE_PATH)
            return f"state already_stopped app={app_name}"
        raise
    if target_kind == "steam_game":
        mark_game_stopped(app_name, GAME_STATE_PATH)
    return f"verified window closed={app_name}"


def _validated_process_names(value: str) -> set[str]:
    names = value.split("|")
    if not names or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in names):
        raise ValueError("Invalid allowlisted process name")
    return {normalized for name in names if (normalized := normalize_process_name(name))}


def _process_name(process_id: int) -> str | None:
    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
    if not process:
        return None
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return None
        return Path(buffer.value).stem.casefold()
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


def _matching_title_process_names(
    app_name: str,
    window_titles: list[str] | None = None,
) -> list[str]:
    names: list[str] = []
    windows = (
        _matching_profile_title_windows(app_name, window_titles)
        if window_titles
        else _matching_title_windows(app_name)
    )
    for hwnd in windows:
        process_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        name = _process_name(process_id.value)
        if name and re.fullmatch(r"[A-Za-z0-9_.-]+", name) and name not in names:
            names.append(name)
    return names


def _find_window_for_processes(value: str) -> int:
    allowed = _validated_process_names(value)
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def callback(hwnd, _lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        if ctypes.windll.user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        process_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if _process_name(process_id.value) in allowed:
            matches.append(int(hwnd))
            return False
        return True

    ctypes.windll.user32.EnumWindows(callback, 0)
    if not matches:
        raise RuntimeError("Application is not running or has no visible window")
    return matches[0]


def _show_window(hwnd: int, operation: str) -> None:
    commands = {"minimize": 6, "maximize": 3, "restore": 9}
    if operation == "focus":
        ctypes.windll.user32.ShowWindowAsync(hwnd, commands["restore"])
        ctypes.windll.user32.BringWindowToTop(hwnd)
        if not ctypes.windll.user32.SetForegroundWindow(hwnd):
            raise RuntimeError("Windows prevented the application from receiving focus")
        return
    command = commands.get(operation)
    if command is None:
        raise ValueError(f"Unknown window operation: {operation}")
    # ShowWindowAsync returns the window's previous visibility state, not a
    # success flag. A zero result is therefore valid for a hidden/minimized
    # window and must not be treated as an operation failure.
    ctypes.windll.user32.ShowWindowAsync(hwnd, command)


def _find_catalog_window(value: str) -> int:
    try:
        target = json.loads(value)
    except json.JSONDecodeError:
        # Backward compatibility for actions created by older releases.
        return _find_window_for_processes(value)
    try:
        app_name = str(target["name"])
        process_names = target.get("processes", [])
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid catalog window target") from exc
    if not isinstance(process_names, list):
        raise ValueError("Invalid catalog process list")
    profile = profile_for(app_name, PROFILE_PATH)
    if profile.preferred_processes:
        valid_names = list(profile.preferred_processes)
    else:
        valid_names = [str(name) for name in process_names]
        known_names = {normalized for name in valid_names if (normalized := normalize_process_name(name))}
        valid_names.extend(
            name
            for name in learned_process_targets_for(app_name, LEARNED_TARGETS_PATH)
            if normalize_process_name(name) not in known_names
        )
    if valid_names:
        try:
            return _find_window_for_processes("|".join(valid_names))
        except RuntimeError:
            pass
    windows = _matching_profile_title_windows(app_name, profile.window_titles)
    if not windows:
        raise RuntimeError("Application is not running or has no visible window")
    return windows[0]


def _control_window(action_id: str, value: str) -> None:
    operation = action_id.removeprefix("window_")
    hwnd = _find_catalog_window(value)
    _show_window(hwnd, operation)


def execute_action(action: SystemAction) -> str | None:
    if action.action_id == "open_shell":
        os.startfile(f"shell:{action.value}")  # type: ignore[attr-defined]
        return None
    if action.action_id == "open_uri":
        if not action.value.startswith("ms-settings:"):
            raise ValueError("Only fixed Windows Settings URIs are allowed")
        os.startfile(action.value)  # type: ignore[attr-defined]
        return None
    if action.action_id == "hotkey":
        _press_hotkey(action.value)
        return None
    if action.action_id == "brightness":
        return f"brightness={_adjust_brightness(int(action.value))}%"
    if action.action_id == "radio":
        return _set_radio(action.value)
    if action.action_id == "airplane_mode":
        return _set_airplane_mode(action.value)
    if action.action_id == "media_key":
        _control_media(action.value)
        return None
    if action.action_id == "volume_up":
        _press_media_key(0xAF, 2)
        return None
    if action.action_id == "volume_down":
        _press_media_key(0xAE, 2)
        return None
    if action.action_id == "volume_mute":
        _press_media_key(0xAD)
        return None
    if action.action_id == "screenshot":
        destination = Path.home() / "Pictures" / "Gela Screenshots"
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
        ImageGrab.grab().save(path)
        return str(path)
    if action.action_id == "lock_windows":
        if not ctypes.windll.user32.LockWorkStation():
            raise OSError("Windows lock request failed")
        return None
    if action.action_id == "power_shutdown":
        subprocess.run(
            ["shutdown.exe", "/s", "/t", "5"],
            check=True,
            **hidden_process_kwargs(),
        )
        return "shutdown scheduled in 5 seconds"
    if action.action_id == "power_restart":
        subprocess.run(
            ["shutdown.exe", "/r", "/t", "5"],
            check=True,
            **hidden_process_kwargs(),
        )
        return "restart scheduled in 5 seconds"
    if action.action_id == "power_sleep":
        if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
            raise OSError("Windows sleep request failed")
        return "sleep requested"
    if action.action_id == "close_process":
        _close_process_windows(action.value)
        return None
    if action.action_id == "close_app":
        return _close_catalog_app(action.value)
    if action.action_id in {"window_focus", "window_minimize", "window_maximize", "window_restore"}:
        _control_window(action.action_id, action.value)
        return None
    if action.action_id == "window_active":
        hwnd = int(ctypes.windll.user32.GetForegroundWindow())
        if not hwnd:
            raise RuntimeError("No active window")
        _show_window(hwnd, action.value)
        return None
    raise ValueError(f"Unknown system action: {action.action_id}")
