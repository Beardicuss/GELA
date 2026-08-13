param(
    [switch]$RequireSigning
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$compilerCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "D:\Inno Setup 6\ISCC.exe"
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup compiler was not found. Install Inno Setup and rerun this script."
}
[string]$configuredThumbprint = $env:GELA_SIGNING_THUMBPRINT
$signingThumbprint = ($configuredThumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
$signingEnabled = [bool]$signingThumbprint
if ($RequireSigning -and -not $signingEnabled) {
    throw "A signed release was required, but GELA_SIGNING_THUMBPRINT is not configured."
}

& (Join-Path $PSScriptRoot "build_release.ps1")
if ($LASTEXITCODE -ne 0) { throw "Portable release build failed" }

$portable = Join-Path $projectRoot "release\Gela-Windows-x64.zip"
if ($signingEnabled) {
    $application = Join-Path $projectRoot "dist\Gela\Gela.exe"
    & (Join-Path $PSScriptRoot "sign_artifacts.ps1") -Path $application -Thumbprint $signingThumbprint
    if ($LASTEXITCODE -ne 0) { throw "Application signing failed" }
    if (Test-Path -LiteralPath $portable) { Remove-Item -LiteralPath $portable -Force }
    Compress-Archive -Path (Join-Path $projectRoot "dist\Gela") -DestinationPath $portable -CompressionLevel Optimal
}

& $compiler (Join-Path $projectRoot "installer\Gela.iss")
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed" }

$installer = Join-Path $projectRoot "release\Gela-Setup-1.5.2-x64.exe"
if (-not (Test-Path -LiteralPath $installer)) { throw "Installer output is missing" }
if ($signingEnabled) {
    & (Join-Path $PSScriptRoot "sign_artifacts.ps1") -Path $installer -Thumbprint $signingThumbprint
    if ($LASTEXITCODE -ne 0) { throw "Installer signing failed" }
}
$artifacts = @($installer, $portable) | ForEach-Object {
    $item = Get-Item -LiteralPath $_
    [ordered]@{
        file = $item.Name
        bytes = $item.Length
        sha256 = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    product = "Gela Voice Assistant"
    publisher = "Softcurse Systems"
    website = "https://softcurse-website.pages.dev/"
    version = "1.5.2"
    architecture = "x64"
    signing = [ordered]@{
        signed = $signingEnabled
        certificate_thumbprint = $(if ($signingEnabled) { $signingThumbprint } else { $null })
        timestamp_url = $(if ($signingEnabled) { $(if ($env:GELA_TIMESTAMP_URL) { $env:GELA_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }) } else { $null })
    }
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    artifacts = $artifacts
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $projectRoot "release\release-manifest.json") -Encoding utf8
$artifacts | ForEach-Object { "$($_.sha256)  $($_.file)" } | Set-Content -LiteralPath (Join-Path $projectRoot "release\SHA256SUMS.txt") -Encoding ascii
Write-Host "Installer created: $installer"
