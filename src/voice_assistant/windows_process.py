from __future__ import annotations

import subprocess
import sys


def hidden_process_kwargs() -> dict[str, int]:
    """Return subprocess flags that prevent console windows on Windows."""
    if sys.platform != "win32":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW}
