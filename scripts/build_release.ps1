$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$icon = Join-Path $projectRoot "assets\icons\gela_tray.ico"
$release = Join-Path $projectRoot "release"
$archive = Join-Path $release "Gela-Windows-x64.zip"

if (-not (Test-Path $python)) {
    throw "Virtual environment is missing: $python"
}
foreach ($model in @("vosk-model-small-en-us-0.15", "vosk-model-small-ka-0.42")) {
    if (-not (Test-Path (Join-Path $projectRoot "models\$model"))) {
        throw "Required model is missing: $model"
    }
}
foreach ($file in @("model.int8.onnx", "tokens.txt")) {
    if (-not (Test-Path (Join-Path $projectRoot "models\omnilingual-asr-300m-int8\$file"))) {
        throw "Required Omnilingual command model file is missing: $file"
    }
}
if (-not (Test-Path $icon)) {
    throw "Package icon is missing: $icon"
}

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

& $python (Join-Path $PSScriptRoot "validate_voice.py")
if ($LASTEXITCODE -ne 0) { throw "Voice response validation failed" }

& (Join-Path $PSScriptRoot "clean_package_metadata.ps1")

& $python -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "Gela.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

New-Item -ItemType Directory -Force -Path $release | Out-Null
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path (Join-Path $projectRoot "dist\Gela") -DestinationPath $archive -CompressionLevel Optimal
Write-Host "Release created: $archive"
