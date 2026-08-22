from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from voice_assistant import private_network


def completed(arguments: list[str], stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def test_private_network_status_detects_connected_https_bridge(monkeypatch):
    monkeypatch.setattr(private_network, "find_tailscale_cli", lambda: Path("tailscale.exe"))
    monkeypatch.setattr(private_network, "_cached_at", 0.0)

    def run(_cli, arguments, timeout=6):
        if arguments == ["status", "--json"]:
            return completed(arguments, json.dumps({
                "BackendState": "Running",
                "Self": {
                    "DNSName": "desktop.example.ts.net.",
                    "TailscaleIPs": ["100.100.10.20", "fd7a::1"],
                },
            }))
        assert arguments == ["serve", "status", "--json"]
        return completed(arguments, json.dumps({"Web": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8765"}}}}))

    monkeypatch.setattr(private_network, "_run_tailscale", run)
    status = private_network.private_network_status(force=True)
    assert status.connected is True
    assert status.ipv4 == "100.100.10.20"
    assert status.dns_name == "desktop.example.ts.net"
    assert status.serve_enabled is True
    assert status.remote_base_url == "https://desktop.example.ts.net"


def test_enable_private_network_uses_private_https_serve(monkeypatch):
    monkeypatch.setattr(private_network, "find_tailscale_cli", lambda: Path("tailscale.exe"))
    statuses = iter([
        private_network.PrivateNetworkStatus(installed=True, connected=True),
        private_network.PrivateNetworkStatus(
            installed=True,
            connected=True,
            serve_enabled=True,
            remote_base_url="https://desktop.example.ts.net",
        ),
    ])
    monkeypatch.setattr(private_network, "private_network_status", lambda force=False: next(statuses))
    calls = []

    def run(_cli, arguments, timeout=6):
        calls.append((arguments, timeout))
        return completed(arguments)

    monkeypatch.setattr(private_network, "_run_tailscale", run)
    status = private_network.enable_private_network_access()
    assert status.remote_base_url == "https://desktop.example.ts.net"
    assert calls == [(["serve", "--bg", "--https=443", "--yes", "127.0.0.1:8765"], 15)]


def test_enable_private_network_requires_installed_connected_client(monkeypatch):
    monkeypatch.setattr(private_network, "find_tailscale_cli", lambda: None)
    with pytest.raises(RuntimeError, match="Install Tailscale"):
        private_network.enable_private_network_access()
