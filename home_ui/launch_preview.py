"""Open Gela Home in a dedicated Edge app window without changing Windows startup.

Run from the repository with .venv/Scripts/python.exe home_ui/launch_preview.py.
The server is private to this window and is stopped when the launcher exits.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


HOME = Path(__file__).resolve().parent
RUNTIME = HOME / ".runtime"
STANDALONE_SERVER = HOME / "server.js" if (HOME / "server.js").is_file() else HOME / ".next" / "standalone" / "server.js"


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_home(url: str, server: subprocess.Popen[bytes], timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Gela Home server stopped during startup. See .runtime/home_server.log.")
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200 and b"Gela Home" in response.read(32_768):
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Gela Home did not become ready. See .runtime/home_server.log.")


def stop_server(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


@contextmanager
def launcher_lock():
    """Keep a second app window from reusing Edge's dedicated profile."""
    import msvcrt

    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "launcher.lock").open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("A Gela Home app window is already open.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _run_unlocked(*, check_only: bool = False) -> int:
    if os.name != "nt":
        raise RuntimeError("This preview launcher currently supports Windows only.")
    if not STANDALONE_SERVER.is_file() or not (STANDALONE_SERVER.parent / ".next" / "static").is_dir():
        raise RuntimeError("Gela Home is not built. Run npm ci and npm run build in home_ui first.")
    node = str(HOME / "node.exe") if (HOME / "node.exe").is_file() else shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is not on PATH.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    backend_hint = HOME / "gela_project_root.txt"
    backend_root = backend_hint.read_text(encoding="utf-8").strip() if backend_hint.is_file() else str(HOME.parent)
    port = free_loopback_port()
    url = f"http://127.0.0.1:{port}/"
    with (RUNTIME / "home_server.log").open("ab") as log:
        server = subprocess.Popen(
            [node, str(STANDALONE_SERVER)],
            cwd=HOME,
            env={**os.environ, "HOSTNAME": "127.0.0.1", "PORT": str(port), "GELA_PROJECT_ROOT": backend_root},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            wait_for_home(url, server)
            if check_only:
                print(f"Gela Home server smoke test passed at {url}")
                return 0
            profile = RUNTIME / "webview-profile"
            profile.mkdir(parents=True, exist_ok=True)
            import webview

            webview.create_window(
                "Gela Home", url=url, fullscreen=True, frameless=True,
                resizable=False, easy_drag=False, background_color="#0a0909",
            )
            print(f"Gela Home opened at {url}. Close its window to stop this preview.", flush=True)
            webview.start(gui="edgechromium", debug=False, private_mode=False, storage_path=str(profile))
            return 0
        finally:
            stop_server(server)


def run(*, check_only: bool = False) -> int:
    if os.name != "nt":
        raise RuntimeError("This preview launcher currently supports Windows only.")
    if check_only:
        return _run_unlocked(check_only=True)
    with launcher_lock():
        return _run_unlocked(check_only=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Gela Home as a recoverable desktop preview")
    parser.add_argument("--check", action="store_true", help="smoke-test the private server without opening a window")
    args = parser.parse_args()
    try:
        return run(check_only=args.check)
    except (OSError, RuntimeError) as exc:
        print(f"Gela Home could not start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
