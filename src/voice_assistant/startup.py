from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from .config import PROJECT_ROOT
from .windows_process import hidden_process_kwargs


SHORTCUT_NAME = "Simple Voice Assistant.lnk"
STARTUP_TASK_NAME = "Gela Voice Assistant"


def _powershell_single_quoted(value: str | Path) -> str:
    return str(value).replace("'", "''")


def startup_shortcut() -> Path:
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    return startup / SHORTCUT_NAME


def _task_exists() -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", STARTUP_TASK_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        **hidden_process_kwargs(),
    )
    return result.returncode == 0


def startup_enabled() -> bool:
    """Return true for the immediate task or a legacy Startup-folder shortcut."""
    return _task_exists() or startup_shortcut().is_file()


def install_startup() -> str:
    """Run Gela immediately at interactive logon, bypassing Startup-folder delay."""
    shortcut = startup_shortcut()
    frozen = getattr(sys, "frozen", False)
    target = Path(sys.executable) if frozen else Path(sys.executable).with_name("pythonw.exe")
    arguments = "--supervise" if frozen else "-m voice_assistant.tray --supervise"
    working_directory = target.parent if frozen else PROJECT_ROOT
    target_value = _powershell_single_quoted(target)
    arguments_value = _powershell_single_quoted(arguments)
    working_directory_value = _powershell_single_quoted(working_directory)
    task_value = _powershell_single_quoted(STARTUP_TASK_NAME)
    script = (
        f"$a=New-ScheduledTaskAction -Execute '{target_value}' -Argument '{arguments_value}' "
        f"-WorkingDirectory '{working_directory_value}';"
        "$t=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;"
        "$p=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) "
        "-LogonType Interactive -RunLevel Limited;"
        "$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
        f"Register-ScheduledTask -TaskName '{task_value}' -Action $a -Trigger $t "
        "-Principal $p -Settings $s -Force | Out-Null"
    )
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-Command", script,
        ],
        capture_output=True,
        text=True,
        check=False,
        **hidden_process_kwargs(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Could not register Gela startup task.")
    shortcut.unlink(missing_ok=True)
    return STARTUP_TASK_NAME


def uninstall_startup() -> bool:
    removed = False
    if _task_exists():
        result = subprocess.run(
            ["schtasks.exe", "/Delete", "/TN", STARTUP_TASK_NAME, "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            **hidden_process_kwargs(),
        )
        removed = result.returncode == 0
    shortcut = startup_shortcut()
    if shortcut.exists():
        shortcut.unlink()
        removed = True
    return removed
