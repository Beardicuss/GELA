param(
    [string]$Ffmpeg = "ffmpeg"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "audio\voice\raw"
$processedRoot = Join-Path $projectRoot "audio\voice\processed"
$manifestPath = Join-Path $projectRoot "audio\voice\recording_manifest.csv"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Path $processedRoot -Force | Out-Null

try {
    $ffmpegCommand = Get-Command $Ffmpeg -ErrorAction Stop
    & $ffmpegCommand.Source -version *> $null
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg version check failed" }
} catch {
    throw "A working FFmpeg executable was not found at '$Ffmpeg'. Pass -Ffmpeg with a valid executable path."
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Development Python is missing: $python"
}

$rows = Import-Csv -LiteralPath $manifestPath
if (-not $rows -or ($rows.processed_filename | Sort-Object -Unique).Count -ne $rows.Count) {
    throw "Voice manifest is empty or contains duplicate processed filenames."
}
$rows | ForEach-Object {
    $input = Join-Path $rawRoot $_.raw_filename
    if (-not (Test-Path -LiteralPath $input)) {
        throw "Raw voice source is missing: $input"
    }
    $output = Join-Path $processedRoot $_.processed_filename
    $temporary = $output + ".tmp.wav"
    & $ffmpegCommand.Source -hide_banner -loglevel error -y -i $input `
        -af "silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,loudnorm=I=-18:TP=-1.5:LRA=7" `
        -ar 48000 -ac 1 -c:a pcm_s16le $temporary
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        throw "FFmpeg failed for $input"
    }
    Move-Item -LiteralPath $temporary -Destination $output -Force
    Write-Host "Processed: $($_.raw_filename) -> $($_.processed_filename)"
}

& $python (Join-Path $PSScriptRoot "validate_voice.py")
if ($LASTEXITCODE -ne 0) { throw "Processed voice validation failed" }
