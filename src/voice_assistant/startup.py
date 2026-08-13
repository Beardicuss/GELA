from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from .config import PROJECT_ROOT
from .windows_process import hidden_process_kwargs


SHORTCUT_NAME = "Simple Voice Assistant.lnk"


def _powershell_single_quoted(value: str | Path) -> str:
    return str(value).replace("'", "''")


def startup_shortcut() -> Path:
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    return startup / SHORTCUT_NAME


def install_startup() -> Path:
    shortcut = startup_shortcut()
    frozen = getattr(sys, "frozen", False)
    target = Path(sys.executable) if frozen else Path(sys.executable).with_name("pythonw.exe")
    arguments = "" if frozen else "-m voice_assistant.tray"
    working_directory = target.parent if frozen else PROJECT_ROOT
    shortcut_value = _powershell_single_quoted(shortcut)
    target_value = _powershell_single_quoted(target)
    working_directory_value = _powershell_single_quoted(working_directory)
    script = (
        "$ws=New-Object -ComObject WScript.Shell;"
        f"$s=$ws.CreateShortcut('{shortcut_value}');"
        f"$s.TargetPath='{target_value}';"
        f"$s.Arguments='{arguments}';"
        f"$s.WorkingDirectory='{working_directory_value}';"
        "$s.Description='Gela offline voice assistant';"
        "$s.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        check=True,
        **hidden_process_kwargs(),
    )
    return shortcut


def uninstall_startup() -> bool:
    shortcut = startup_shortcut()
    if shortcut.exists():
        shortcut.unlink()
        return True
    return False
