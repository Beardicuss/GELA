$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $projectRoot ".venv"
$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
    "C:\Program Files\Python313\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe"
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw "A regular Python 3.11-3.13 installation was not found. Install Python from python.org; Microsoft Store Python is not supported for Gela development because it redirects LocalAppData."
}

$basePrefix = & $python -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0 -or $basePrefix -match "WindowsApps[\\/]PythonSoftwareFoundation\.Python") {
    throw "Microsoft Store Python cannot be used for Gela development because it creates a separate virtualized LocalAppData copy."
}

if (Test-Path -LiteralPath $venv) {
    $configuration = Get-Content -LiteralPath (Join-Path $venv "pyvenv.cfg") -Raw
    if ($configuration -match "WindowsApps[\\/]PythonSoftwareFoundation\.Python") {
        throw "The existing .venv uses Microsoft Store Python. Rename or remove that .venv, then run this script again."
    }
} else {
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv" }
}

$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip" }
& $venvPython -m pip install -e "$projectRoot[dev]"
if ($LASTEXITCODE -ne 0) { throw "Could not install Gela development dependencies" }
& (Join-Path $PSScriptRoot "clean_package_metadata.ps1")
& $venvPython -c "import json, sys; from voice_assistant.config import USER_DATA_ROOT; p=USER_DATA_ROOT / 'config/apps.json'; print('Python:', sys.version.split()[0]); print('Gela data:', USER_DATA_ROOT); print('Catalog entries:', len(json.loads(p.read_bytes().decode('utf-8'))) if p.is_file() else 0)"
if ($LASTEXITCODE -ne 0) { throw "The new environment could not read Gela's shared user data" }
