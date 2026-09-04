param(
    [Parameter(Mandatory = $true)][string]$Port
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frames = Join-Path $root "build\board_frames"
$firmware = Join-Path $root "firmware"
$projectRoot = Split-Path -Parent (Split-Path -Parent $root)
$mpremote = Join-Path $projectRoot ".venv\Scripts\mpremote.exe"

if (-not (Test-Path -LiteralPath (Join-Path $frames "idle_0.png"))) {
    throw "Converted frames are missing. Run tools\convert_frames.py first."
}
if (-not (Test-Path -LiteralPath $mpremote)) {
    throw "mpremote is not installed. Install it with: python -m pip install mpremote"
}

& $mpremote connect $Port exec "import os; 'gela_frames' in os.listdir('/') or os.mkdir('/gela_frames')"
Get-ChildItem -LiteralPath $frames -Filter *.png | ForEach-Object {
    & $mpremote connect $Port fs cp $_.FullName (":gela_frames/" + $_.Name)
}
& $mpremote connect $Port fs cp (Join-Path $firmware "face_animation.py") :face_animation.py
& $mpremote connect $Port fs cp (Join-Path $firmware "main.py") :main.py
& $mpremote connect $Port reset
