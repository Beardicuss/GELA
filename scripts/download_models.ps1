param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelsRoot = Join-Path $projectRoot "models"

$models = @(
    @{ Name = "vosk-model-small-en-us-0.15"; Url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" },
    @{ Name = "vosk-model-small-ka-0.42"; Url = "https://alphacephei.com/vosk/models/vosk-model-small-ka-0.42.zip" }
)

New-Item -ItemType Directory -Path $modelsRoot -Force | Out-Null

foreach ($model in $models) {
    $destination = Join-Path $modelsRoot $model.Name
    if ((Test-Path -LiteralPath $destination) -and -not $Force) {
        Write-Host "Already installed: $($model.Name)"
        continue
    }

    $archive = Join-Path ([System.IO.Path]::GetTempPath()) "$($model.Name).zip"
    try {
        Write-Host "Downloading $($model.Name)..."
        Invoke-WebRequest -Uri $model.Url -OutFile $archive
        if (Test-Path -LiteralPath $destination) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        Expand-Archive -LiteralPath $archive -DestinationPath $modelsRoot -Force
        Write-Host "Installed: $destination"
    }
    finally {
        Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    }
}

