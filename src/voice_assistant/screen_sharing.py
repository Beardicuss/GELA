from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from io import BytesIO
import ipaddress
import json
from pathlib import Path
import threading
import time

from PIL import Image, ImageGrab

from .config import USER_DATA_ROOT
from .storage import atomic_write_text


SCREEN_PERMISSION_PATH = USER_DATA_ROOT / "mobile" / "screen_sharing_permission.json"
SCREEN_PERMISSION_SECONDS = 15 * 60
MAX_SCREEN_WIDTH = 1280
MAX_SCREEN_HEIGHT = 720
MIN_JPEG_QUALITY = 40
MAX_JPEG_QUALITY = 75


@dataclass(frozen=True)
class ScreenSharingStatus:
    authorized: bool
    expires_at: str | None = None
    remaining_seconds: int = 0
    remote_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_capture_lock = threading.Lock()


def is_private_proxy_source(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def screen_sharing_status(path: Path = SCREEN_PERMISSION_PATH) -> ScreenSharingStatus:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        expires_epoch = float(payload.get("expires_epoch", 0)) if isinstance(payload, dict) else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        expires_epoch = 0
    remaining = max(0, int(expires_epoch - time.time()))
    if not remaining:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return ScreenSharingStatus(authorized=False)
    return ScreenSharingStatus(
        authorized=True,
        expires_at=datetime.fromtimestamp(expires_epoch).astimezone().isoformat(timespec="seconds"),
        remaining_seconds=remaining,
    )


def grant_screen_sharing(
    path: Path = SCREEN_PERMISSION_PATH,
    duration_seconds: int = SCREEN_PERMISSION_SECONDS,
) -> ScreenSharingStatus:
    duration = min(max(int(duration_seconds), 60), SCREEN_PERMISSION_SECONDS)
    expires_epoch = time.time() + duration
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps({"expires_epoch": expires_epoch}, indent=2) + "\n")
    return screen_sharing_status(path)


def revoke_screen_sharing(path: Path = SCREEN_PERMISSION_PATH) -> ScreenSharingStatus:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return ScreenSharingStatus(authorized=False)


def capture_screen_jpeg(width: int, height: int, quality: int, all_screens: bool = False) -> tuple[bytes, int, int]:
    target_width = min(max(int(width), 320), MAX_SCREEN_WIDTH)
    target_height = min(max(int(height), 180), MAX_SCREEN_HEIGHT)
    jpeg_quality = min(max(int(quality), MIN_JPEG_QUALITY), MAX_JPEG_QUALITY)
    with _capture_lock:
        image = ImageGrab.grab(include_layered_windows=True, all_screens=all_screens)
        image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        if image.mode != "RGB":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=jpeg_quality, optimize=False)
        return output.getvalue(), image.width, image.height
