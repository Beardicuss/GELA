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

Hardware tests will be added separately under `microbit/` because they require a
physical board. Each hardware phase must also provide a host-side simulator so
the protocol and safety behaviour remain testable in GitHub Actions.

GitHub Actions runs the suite on Windows with Python 3.11, 3.12, and 3.13 for
every pull request and push to `main`.
