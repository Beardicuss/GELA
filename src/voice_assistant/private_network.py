from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time


TAILSCALE_DOWNLOAD_URL = "https://tailscale.com/download/windows"
TAILSCALE_STATUS_CACHE_SECONDS = 10


@dataclass(frozen=True)
class PrivateNetworkStatus:
    installed: bool = False
    connected: bool = False
    ipv4: str | None = None
    dns_name: str | None = None
    serve_enabled: bool = False
    remote_base_url: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_cache_lock = threading.Lock()
_cached_at = 0.0
_cached_status = PrivateNetworkStatus()


def _tailscale_service_cli() -> Path | None:
    """Resolve non-default Windows installs from the Tailscale service path."""
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Tailscale",
        ) as key:
            image_path = str(winreg.QueryValueEx(key, "ImagePath")[0]).strip()
    except (OSError, ImportError):
        return None
    if image_path.startswith('"'):
        executable = image_path.split('"', 2)[1]
    else:
        executable = image_path.split(maxsplit=1)[0]
    daemon = Path(os.path.expandvars(executable))
    cli = daemon.with_name("tailscale.exe")
    return cli if cli.is_file() else None


def find_tailscale_cli() -> Path | None:
    candidates = [
        shutil.which("tailscale.exe"),
        _tailscale_service_cli(),
        str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Tailscale" / "tailscale.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def _run_tailscale(cli: Path, arguments: list[str], timeout: int = 6) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cli), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _contains_bridge_target(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_bridge_target(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_bridge_target(item) for item in value)
    return isinstance(value, str) and "8765" in value and ("127.0.0.1" in value or "localhost" in value)


def private_network_status(*, force: bool = False) -> PrivateNetworkStatus:
    global _cached_at, _cached_status
    now = time.monotonic()
    with _cache_lock:
        if not force and now - _cached_at < TAILSCALE_STATUS_CACHE_SECONDS:
            return _cached_status
        cli = find_tailscale_cli()
        if cli is None:
            status = PrivateNetworkStatus(error="Tailscale is not installed.")
        else:
            try:
                result = _run_tailscale(cli, ["status", "--json"])
                if result.returncode != 0:
                    status = PrivateNetworkStatus(installed=True, error="Tailscale is installed but not connected.")
                else:
                    payload = json.loads(result.stdout)
                    self_status = payload.get("Self") if isinstance(payload, dict) else None
                    self_status = self_status if isinstance(self_status, dict) else {}
                    backend_state = str(payload.get("BackendState", "")) if isinstance(payload, dict) else ""
                    addresses = self_status.get("TailscaleIPs")
                    addresses = addresses if isinstance(addresses, list) else []
                    ipv4 = next((str(item) for item in addresses if str(item).startswith("100.")), None)
                    dns_name = str(self_status.get("DNSName", "")).strip().rstrip(".") or None
                    connected = backend_state == "Running" and bool(ipv4)
                    serve_enabled = False
                    if connected:
                        serve = _run_tailscale(cli, ["serve", "status", "--json"])
                        if serve.returncode == 0 and serve.stdout.strip():
                            try:
                                serve_enabled = _contains_bridge_target(json.loads(serve.stdout))
                            except json.JSONDecodeError:
                                serve_enabled = False
                    remote_base_url = f"https://{dns_name}" if connected and serve_enabled and dns_name else None
                    status = PrivateNetworkStatus(
                        installed=True,
                        connected=connected,
                        ipv4=ipv4,
                        dns_name=dns_name,
                        serve_enabled=serve_enabled,
                        remote_base_url=remote_base_url,
                        error=None if connected else "Tailscale is not signed in or connected.",
                    )
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
                status = PrivateNetworkStatus(installed=True, error="Could not read Tailscale status.")
        _cached_status = status
        _cached_at = now
        return status


def enable_private_network_access() -> PrivateNetworkStatus:
    cli = find_tailscale_cli()
    if cli is None:
        raise RuntimeError("Install Tailscale on Windows first.")
    current = private_network_status(force=True)
    if not current.connected:
        raise RuntimeError("Sign in to Tailscale on Windows before enabling remote access.")
    result = _run_tailscale(
        cli,
        ["serve", "--bg", "--https=443", "--yes", "127.0.0.1:8765"],
        timeout=15,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise RuntimeError(message[:300] or "Tailscale Serve could not be enabled.")
    status = private_network_status(force=True)
    if not status.remote_base_url:
        raise RuntimeError("Tailscale enabled the service, but its private HTTPS address is not ready yet.")
    return status
