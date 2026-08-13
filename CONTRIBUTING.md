# Contributing to GELA

Thank you for helping improve GELA. The project focuses on dependable, offline,
short-command control of Windows in Georgian.

## Before opening a change

1. Search existing issues and pull requests.
2. Open an issue before a large architectural or hardware change.
3. Do not include speech models, installers, logs, credentials, private machine
   catalogs, or absolute paths from your PC.
4. Keep command execution allowlisted and wake-gated.

## Development setup

```powershell
.\scripts\setup_dev.ps1
.\scripts\download_models.ps1
.\.venv\Scripts\python.exe -m pytest -q
```

Python 3.11 through 3.13 on Windows is supported. See `README.md` for model and
microphone setup.

## Pull requests

- Keep each pull request focused.
- Add or update tests for behaviour changes.
- Run the entire test suite.
- Update `CHANGELOG.md` under **Unreleased** when behaviour changes.
- Explain any new network access, background process, dependency, or Windows
  privilege requirement.
- Preserve Georgian text as UTF-8.

By submitting a contribution, you agree to the contribution terms in
`LICENSE.md` and to the community expectations in `CODE_OF_CONDUCT.md`.
