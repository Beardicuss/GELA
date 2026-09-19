$ErrorActionPreference = "Stop"

$homeRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $homeRoot
$standalone = Join-Path $homeRoot ".next\standalone"
$releaseRoot = Join-Path $projectRoot "release"
$stage = Join-Path $releaseRoot "Gela-Home-preview"

if (-not (Test-Path -LiteralPath (Join-Path $standalone "server.js"))) {
    throw "Build Gela Home first: npm run build in home_ui"
}
$node = (Get-Command node -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $node)) { throw "Node.js executable was not found" }

New-Item -ItemType Directory -Force -Path $stage | Out-Null
Get-ChildItem -LiteralPath $standalone -Force | Copy-Item -Destination $stage -Recurse -Force
Copy-Item -LiteralPath $node -Destination (Join-Path $stage "node.exe") -Force
Copy-Item -LiteralPath (Join-Path $homeRoot "launch_preview.py") -Destination (Join-Path $stage "launch_preview.py") -Force
[System.IO.File]::WriteAllText(
    (Join-Path $stage "gela_project_root.txt"),
    $projectRoot,
    [System.Text.UTF8Encoding]::new($false)
)
$homeConfigRoot = Join-Path $env:LOCALAPPDATA "Gela\home"
$homeConfig = Join-Path $homeConfigRoot "bundle_path.json"
if (-not (Test-Path -LiteralPath $homeConfig)) {
    New-Item -ItemType Directory -Force -Path $homeConfigRoot | Out-Null
    $setting = @{ path = $stage } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($homeConfig, $setting, [System.Text.UTF8Encoding]::new($false))
} else {
    Write-Host "Existing Gela Home bundle preference preserved: $homeConfig"
}
$runtimePath = Join-Path $stage ".runtime"
$bytes = (Get-ChildItem -LiteralPath $stage -Recurse -File |
    Where-Object { -not $_.FullName.StartsWith($runtimePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) } |
    Measure-Object -Property Length -Sum).Sum
Write-Host ("Staged Gela Home on D: {0} ({1:N1} MB excluding browser profile)" -f $stage, ($bytes / 1MB))
Write-Host "This is a local preview bound to this Gela source tree, not a distributable installer."
