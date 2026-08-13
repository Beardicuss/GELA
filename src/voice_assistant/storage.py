from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil


def replace_file(source: Path, destination: Path) -> None:
    """Replace a file, tolerating Microsoft Store Python path virtualization."""
    try:
        os.replace(source, destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
            raise
        shutil.copy2(source, destination)
        source.unlink()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding=encoding)
    replace_file(temporary, path)
