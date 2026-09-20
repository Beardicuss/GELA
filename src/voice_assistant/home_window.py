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
HOME_WINDOW_TITLE = "Gela Home"

BOOT_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#020202;color:#e8f4f8}
body{font-family:Consolas,"Segoe UI",sans-serif;background:radial-gradient(ellipse at 50% 46%,#072b3d 0,#03131f 38%,#01050a 72%,#020202 100%)}
.grid{position:fixed;inset:0;opacity:.22;background-image:linear-gradient(rgba(0,255,255,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(0,136,255,.07) 1px,transparent 1px);background-size:48px 48px;mask-image:radial-gradient(circle at center,#000,transparent 80%)}
.scan{position:fixed;inset:0;opacity:.07;background:repeating-linear-gradient(0deg,transparent 0 3px,rgba(0,255,255,.2) 4px)}
.frame{position:fixed;inset:28px;border:1px solid rgba(0,255,255,.2);clip-path:polygon(0 0,34% 0,35% 14px,65% 14px,66% 0,100% 0,100% 100%,66% 100%,65% calc(100% - 14px),35% calc(100% - 14px),34% 100%,0 100%)}
.brand{position:fixed;top:30px;left:38px;color:#00ffff;font-size:10px;letter-spacing:.34em;text-shadow:0 0 14px #00ffff}.brand b{color:#00ffc8}
.core{position:fixed;left:50%;top:46%;width:186px;height:186px;transform:translate(-50%,-50%);border:1px solid rgba(0,255,255,.55);border-radius:50%;box-shadow:0 0 36px rgba(0,255,255,.15),inset 0 0 36px rgba(0,136,255,.12);animation:pulse 2s ease-in-out infinite}
.core:before,.core:after{content:"";position:absolute;border-radius:50%;inset:22px;border:1px dashed rgba(0,255,255,.28);animation:spin 7s linear infinite}.core:after{inset:58px;border:0;background:#00ffff;box-shadow:0 0 14px #00ffff,0 0 60px rgba(0,255,255,.75);animation:pulse 1.4s ease-in-out infinite}
.status{position:fixed;left:50%;top:calc(46% + 130px);transform:translateX(-50%);text-align:center;letter-spacing:.28em;font-size:11px;color:#00ffc8}.line{width:340px;height:1px;margin:14px auto;background:linear-gradient(90deg,transparent,#00ffff,transparent);box-shadow:0 0 12px #00ffff}.sub{font-size:9px;color:rgba(232,244,248,.48);letter-spacing:.2em}
.telemetry{position:fixed;left:38px;bottom:34px;color:rgba(232,244,248,.45);font-size:9px;line-height:1.8;letter-spacing:.14em}.telemetry i{color:#ff9500;font-style:normal}
@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{50%{opacity:.62;filter:brightness(1.4)}}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
</style></head><body><div class="grid"></div><div class="scan"></div><div class="frame"></div>
<div class="brand"><b>◆</b> SOFTCURSE SYSTEMS // GELA BOOT</div><div class="core"></div>
<div class="status">INITIALIZING COMMAND NEXUS<div class="line"></div><div class="sub">LOCAL CONTROL · VOICE CORE · HOME SURFACE</div></div>
<div class="telemetry"><i>01</i> SECURE LOCAL SESSION<br><i>02</i> STARTING GELA SERVICES<br><i>03</i> MATERIALIZING HOME INTERFACE</div>
</body></html>"""


def _visit_home_windows(visitor) -> int:
    """Visit every Gela Home top-level window in the current Windows session."""
    if os.name != "nt":
        return 0
    user32 = ctypes.windll.user32
    count = 0

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(handle, _parameter):
        nonlocal count
        length = user32.GetWindowTextLengthW(handle)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, title, length + 1)
        if title.value == HOME_WINDOW_TITLE:
            count += 1
            visitor(user32, handle)
        return True

    user32.EnumWindows(visit, None)
    return count


def home_window_exists() -> bool:
    return _visit_home_windows(lambda _user32, _handle: None) > 0


def home_window_visible() -> bool:
    visible = False

    def inspect(user32, handle) -> None:
        nonlocal visible
        visible = visible or bool(user32.IsWindowVisible(handle))

    _visit_home_windows(inspect)
    return visible


def set_home_window_visible(visible: bool) -> bool:
    """Hide Home to reveal Explorer, or restore it without creating a taskbar button."""
    sw_hide = 0
    sw_show_maximized = 3

    def update(user32, handle) -> None:
        user32.ShowWindowAsync(handle, sw_show_maximized if visible else sw_hide)
        if visible:
            user32.SetForegroundWindow(handle)

    return _visit_home_windows(update) > 0


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
        if title.value != HOME_WINDOW_TITLE:
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
            profile = bundle / ".runtime" / "webview-profile"
            profile.mkdir(parents=True, exist_ok=True)
            import webview

            window = webview.create_window(
                HOME_WINDOW_TITLE, html=BOOT_HTML, fullscreen=True, frameless=True,
                resizable=False, easy_drag=False, background_color="#020202",
                hidden=True,
            )

            revealed = False

            def reveal_home() -> None:
                nonlocal revealed
                if revealed:
                    return
                # A hidden native window already has an HWND, but Explorer has not
                # yet registered it in the taskbar. Apply the tool-window style
                # first, then reveal it as the full-screen Home surface.
                _hide_home_from_taskbar()
                window.show()

                revealed = True

            def load_home() -> None:
                _wait_ready(url, server)
                window.load_url(url)

            window.events.loaded += reveal_home
            webview.start(load_home, gui="edgechromium", debug=False, private_mode=False, storage_path=str(profile))
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
