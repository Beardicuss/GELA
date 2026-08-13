param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [string]$Thumbprint = $env:GELA_SIGNING_THUMBPRINT,
    [ValidateSet("CurrentUser", "LocalMachine")]
    [string]$StoreLocation = $(if ($env:GELA_SIGNING_STORE) { $env:GELA_SIGNING_STORE } else { "CurrentUser" }),
    [string]$ExpectedSubject = "Softcurse Systems",
    [string]$TimestampUrl = $(if ($env:GELA_TIMESTAMP_URL) { $env:GELA_TIMESTAMP_URL } else { "http://timestamp.digicert.com" })
)

$ErrorActionPreference = "Stop"
$normalizedThumbprint = ($Thumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
if (-not $normalizedThumbprint) {
    throw "GELA_SIGNING_THUMBPRINT is required. Select a trusted code-signing certificate with a private key."
}
if ($TimestampUrl -notmatch '^https?://') {
    throw "Timestamp URL must use HTTP or HTTPS."
}

$certificatePath = "Cert:\$StoreLocation\My\$normalizedThumbprint"
$certificate = Get-Item -LiteralPath $certificatePath -ErrorAction SilentlyContinue
if (-not $certificate) {
    throw "Signing certificate was not found: $certificatePath"
}
if (-not $certificate.HasPrivateKey) {
    throw "Signing certificate has no accessible private key: $normalizedThumbprint"
}
$now = Get-Date
if ($certificate.NotBefore -gt $now -or $certificate.NotAfter -le $now) {
    throw "Signing certificate is not currently valid: $($certificate.NotBefore) - $($certificate.NotAfter)"
}
$codeSigningOid = "1.3.6.1.5.5.7.3.3"
if ($certificate.EnhancedKeyUsageList.ObjectId.Value -notcontains $codeSigningOid) {
    throw "Certificate is not authorized for code signing: $normalizedThumbprint"
}
if ($ExpectedSubject -and $certificate.Subject -notlike "*$ExpectedSubject*") {
    throw "Certificate subject '$($certificate.Subject)' does not match expected publisher '$ExpectedSubject'."
}

$sdkRoots = @(
    "C:\Program Files (x86)\Windows Kits\10\bin",
    "C:\Program Files\Windows Kits\10\bin"
)
$signTool = $sdkRoots | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Get-ChildItem -LiteralPath $_ -Filter "signtool.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq "x64" }
} | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signTool) {
    throw "Windows SDK SignTool (x64) was not found."
}

foreach ($item in $Path) {
    $resolved = (Resolve-Path -LiteralPath $item).Path
    $arguments = @("sign", "/s", "My")
    if ($StoreLocation -eq "LocalMachine") { $arguments += "/sm" }
    $arguments += @(
        "/sha1", $normalizedThumbprint,
        "/fd", "SHA256",
        "/tr", $TimestampUrl,
        "/td", "SHA256",
        "/d", "Gela Voice Assistant",
        "/du", "https://softcurse-website.pages.dev/",
        $resolved
    )
    & $signTool.FullName @arguments
    if ($LASTEXITCODE -ne 0) { throw "SignTool failed to sign: $resolved" }
    & $signTool.FullName verify /pa /all /v $resolved
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed: $resolved" }
    $signature = Get-AuthenticodeSignature -LiteralPath $resolved
    if ($signature.Status -ne "Valid") {
        throw "Authenticode verification failed for $resolved`: $($signature.StatusMessage)"
    }
    if ($signature.SignerCertificate.Thumbprint -ne $normalizedThumbprint) {
        throw "Unexpected signer certificate on: $resolved"
    }
    if (-not $signature.TimeStamperCertificate) {
        throw "RFC 3161 timestamp is missing from: $resolved"
    }
    Write-Host "Signed and verified: $resolved"
}
