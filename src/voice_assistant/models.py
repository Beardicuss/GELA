from __future__ import annotations

from pathlib import Path


def validate_model_directory(path: Path) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"Vosk model directory is missing: {path}")
    required = ("am", "conf", "graph")
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        raise RuntimeError(f"Invalid Vosk model at {path}; missing: {', '.join(missing)}")

