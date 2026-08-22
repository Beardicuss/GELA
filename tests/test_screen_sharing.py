from __future__ import annotations

import json
import time

from PIL import Image

from voice_assistant import screen_sharing


def test_screen_permission_is_bounded_and_revocable(tmp_path, monkeypatch):
    path = tmp_path / "permission.json"
    monkeypatch.setattr(time, "time", lambda: 2_000_000_000.0)
    status = screen_sharing.grant_screen_sharing(path, duration_seconds=120)
    assert status.authorized is True
    assert status.remaining_seconds == 120
    assert json.loads(path.read_text(encoding="utf-8"))["expires_epoch"] == 2_000_000_120.0

    monkeypatch.setattr(time, "time", lambda: 2_000_000_121.0)
    assert screen_sharing.screen_sharing_status(path).authorized is False
    assert not path.exists()
    assert screen_sharing.revoke_screen_sharing(path).authorized is False


def test_screen_capture_is_bounded_jpeg(monkeypatch):
    options = []
    monkeypatch.setattr(
        screen_sharing.ImageGrab,
        "grab",
        lambda **capture_options: options.append(capture_options) or Image.new("RGB", (2560, 1440), "#7a1919"),
    )
    content, width, height = screen_sharing.capture_screen_jpeg(900, 500, 90)
    assert content.startswith(b"\xff\xd8")
    assert (width, height) == (889, 500)
    assert len(content) < 100_000
    assert options[-1]["all_screens"] is False
    screen_sharing.capture_screen_jpeg(900, 500, 55, all_screens=True)
    assert options[-1]["all_screens"] is True


def test_screen_frames_accept_only_the_loopback_https_proxy_source():
    assert screen_sharing.is_private_proxy_source("127.0.0.1") is True
    assert screen_sharing.is_private_proxy_source("::1") is True
    assert screen_sharing.is_private_proxy_source("192.168.100.5") is False
    assert screen_sharing.is_private_proxy_source("100.64.0.5") is False
