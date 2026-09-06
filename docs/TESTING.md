# Testing

Install the development dependencies and run the complete suite:

```powershell
.\scripts\setup_dev.ps1
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers parsing, recognition adapters, wake/command control flow,
application and game lifecycle handling, profiles, aliases, catalog maintenance,
responses, settings, runtime state, tray assets, and packaging metadata. Tests
must not require downloaded ASR models, microphone hardware, installed games, or
network access.

Host-side board protocol and firmware-contract tests run in the normal suite.
Physical mPython Board 3.0 validation additionally covers clean boot, Wi-Fi
reconnection, every face asset, repeated push-to-talk commands, mute toggling,
temporary-recording storage headroom, and USB/power-cycle recovery. Hardware-only
checks are documented under `mcu/mpython_board_3_face/` and must retain a
host-testable protocol boundary for GitHub Actions.

GitHub Actions runs the suite on Windows with Python 3.11, 3.12, and 3.13 for
every pull request and push to `main`.

Different-network validation additionally requires two signed-in Tailscale
devices. In the Mobile connection window, enable encrypted remote access, verify
the displayed URL uses HTTPS, then confirm an authenticated Android client works
over mobile data. Restore the LAN and confirm local HTTP remains usable. Verify
that no public Funnel or router port-forward rule was created.

For screen validation, grant the 15-minute permission through biometric mobile
authorization, separately test the PC fallback, and load frames through the
private HTTPS URL. Verify authentication,
permission expiry/revocation, 1280×720 bounds, and `no-store` response headers.
Direct LAN requests must be rejected and the mobile viewer must not control PC
input.
