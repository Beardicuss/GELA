$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$sourceRoot = (Resolve-Path -LiteralPath (Join-Path $projectRoot "src")).Path
$prefix = $sourceRoot.TrimEnd('\') + '\'

Get-ChildItem -LiteralPath $sourceRoot -Directory -Filter "*.egg-info" | ForEach-Object {
    $target = $_.FullName
    if (-not $target.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove package metadata outside the source directory: $target"
    }
    Remove-Item -LiteralPath $target -Recurse -Force
    Write-Host "Removed generated package metadata: $target"
}
