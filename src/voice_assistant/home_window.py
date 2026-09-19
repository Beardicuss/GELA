"""Optional Gela Home window; Explorer and Gela startup stay unchanged."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from .config import PROJECT_ROOT, USER_DATA_ROOT, USER_LOG_ROOT


BUNDLE_CONFIG_PATH = USER_DATA_ROOT / "home" / "bundle_path.json"
SOURCE_BUNDLE = PROJECT_ROOT / "home_ui" / ".next" / "standalone"


def _hide_home_from_taskbar() -> bool:
    """Mark Home as a tool window before it is revealed to the Windows shell."""
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    process_id = os.getpid()
    gwl_exstyle = -20
    ws_ex_toolwindow = 0x00000080
    ws_ex_appwindow = 0x00040000
    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010
    swp_framechanged = 0x0020
    get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)

    styled = False

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(handle, _parameter):
        nonlocal styled
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value != process_id:
            return True
        length = user32.GetWindowTextLengthW(handle)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, title, length + 1)
        if title.value != "Gela Home":
            return True
        style = get_style(handle, gwl_exstyle)
        set_style(handle, gwl_exstyle, (style | ws_ex_toolwindow) & ~ws_ex_appwindow)
        user32.SetWindowPos(
            handle, None, 0, 0, 0, 0,
            swp_nomove | swp_nosize | swp_nozorder | swp_noactivate | swp_framechanged,
        )
        styled = True
        return True

    user32.EnumWindows(visit, None)
    return styled


def _valid_bundle(path: Path) -> bool:
    return (path / "server.js").is_file() and (path / ".next" / "static").is_dir()


def find_home_bundle(config_path: Path = BUNDLE_CONFIG_PATH) -> Path | None:
    try:
        configured = json.loads(config_path.read_text(encoding="utf-8"))
        candidate = Path(configured["path"])
        if candidate.is_absolute() and _valid_bundle(candidate):
            return candidate
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not getattr(sys, "frozen", False) and _valid_bundle(SOURCE_BUNDLE):
        return SOURCE_BUNDLE
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def _window_lock():
    import msvcrt

    path = USER_DATA_ROOT / "home" / "window.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Gela Home is already open.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _wait_ready(url: str, server: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Gela Home server stopped while starting.")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200 and b"Gela Home" in response.read(32_768):
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Gela Home did not become ready within 30 seconds.")


def _stop_server(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def run_home_window() -> None:
    if os.name != "nt":
        raise RuntimeError("Gela Home window currently supports Windows only.")
    bundle = find_home_bundle()
    if bundle is None:
        raise RuntimeError("Gela Home bundle is unavailable. Stage it on D: first.")
    node = bundle / "node.exe"
    node_command = str(node) if node.is_file() else shutil.which("node")
    if not node_command:
        raise RuntimeError("Node.js was not found in the Gela Home bundle or on PATH.")
    backend_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else PROJECT_ROOT
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    USER_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with _window_lock(), (USER_LOG_ROOT / "home_window.log").open("ab") as log:
        server = subprocess.Popen(
            [node_command, str(bundle / "server.js")],
            cwd=bundle,
            env={**os.environ, "HOSTNAME": "127.0.0.1", "PORT": str(port), "GELA_PROJECT_ROOT": str(backend_root)},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            _wait_ready(url, server)
            profile = bundle / ".runtime" / "webview-profile"
            profile.mkdir(parents=True, exist_ok=True)
            import webview

            window = webview.create_window(
                "Gela Home", url=url, fullscreen=True, frameless=True,
                resizable=False, easy_drag=False, background_color="#0a0909",
                hidden=True,
            )

            def reveal_home() -> None:
                # A hidden native window already has an HWND, but Explorer has not
                # yet registered it in the taskbar. Apply the tool-window style
                # first, then reveal it as the full-screen Home surface.
                _hide_home_from_taskbar()
                window.show()

            window.events.loaded += reveal_home
            webview.start(gui="edgechromium", debug=False, private_mode=False, storage_path=str(profile))
        finally:
            _stop_server(server)


def main() -> int:
    try:
        run_home_window()
        return 0
    except Exception as exc:
        logging.exception("Gela Home could not open: %s", exc)
        try:
            USER_LOG_ROOT.mkdir(parents=True, exist_ok=True)
            (USER_LOG_ROOT / "home_window_error.log").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        except OSError:
            pass
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, str(exc), "Gela Home", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
