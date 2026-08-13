# Gela release signing

Public Gela releases must use a publicly trusted Authenticode code-signing certificate issued to Softcurse Systems. Never commit a PFX file, private key, hardware-token credential, or signing-service secret to this project.

## Prerequisites

1. Obtain an OV or EV code-signing certificate for the legal Softcurse Systems publisher identity.
2. Install or synchronize the certificate into `Cert:\CurrentUser\My` (recommended) or `Cert:\LocalMachine\My`. The private key must be accessible to the release account and the certificate must include the Code Signing EKU.
3. Set the certificate thumbprint for the current PowerShell session:

   ```powershell
   $env:GELA_SIGNING_THUMBPRINT = "CERTIFICATE_SHA1_THUMBPRINT"
   ```

4. If the certificate is in the machine store, also set:

   ```powershell
   $env:GELA_SIGNING_STORE = "LocalMachine"
   ```

The default RFC 3161 timestamp service is `http://timestamp.digicert.com`. It can be overridden with `GELA_TIMESTAMP_URL`.

## Signed release

Run:

```powershell
.\scripts\build_installer.ps1 -RequireSigning
```

The pipeline signs and verifies `dist\Gela\Gela.exe` before rebuilding the portable ZIP, compiles the installer around that signed application, then signs and verifies the installer. SHA-256 hashes and signing metadata are written only after signing succeeds. Any missing certificate, publisher mismatch, invalid EKU, absent private key, timestamp failure, or verification failure stops the release.
