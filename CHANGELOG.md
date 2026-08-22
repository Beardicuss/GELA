# Changelog

All notable changes are recorded here. Versions follow semantic versioning where
practical.

## Unreleased

### Added

- Authenticated private-HTTPS screen permission grant/revoke for biometrically confirmed paired phones; PC-side approval remains a fallback.
- Primary-monitor capture by default with an authenticated optional all-screens mode for readable phone scaling.
- Permission-gated, private-HTTPS-only PC screen frames for Mobile's view-only viewer.
- Fifteen-minute screen authorization, immediate revocation, bounded capture, and per-device frame limiting.
- Optional different-network mobile control through a private Tailscale HTTPS Serve endpoint.
- Mobile connection-window status, setup, and copy controls for the encrypted remote address.
- Authenticated bridge metadata used by Mobile to learn and fail over to the remote route.
- Redacted paired-device inventory, authenticated revocation, recoverable token rotation, and bounded credential-free mobile security audit endpoints.
- Token-derived, source-bound rediscovery proof that does not transmit credentials.
- Authenticated, explicit mobile clipboard exchange with bounded UTF-8 text.
- Protected 25 MB mobile file transfer confined to dedicated PC inbox/outbox folders.
- Nested tray shortcut for opening the mobile transfer directory.
- Stable desktop bridge identity and local UDP rediscovery responses.
- Authenticated, bounded mobile PCM transcription using the existing worker model.
- Authenticated mobile pairing/status metadata for local Wake-on-LAN.
- Exact Georgian commands for Windows shutdown, restart, and standby.
- Five-second non-forced shutdown/restart scheduling so Windows can warn about
  unsaved work.

### Planned

- micro:bit V2 USB controller and status prototype.
- Transport-neutral peripheral protocol for future wireless and robot devices.

## 1.5.2 - 2026-08-10

### Fixed

- Added bounded fuzzy correction for close Georgian command transcriptions.
- Added Steam spoken aliases including `სთიმი`, `სტიმი`, and `თიმი`.

### Changed

- Commands use Meta Omnilingual ASR INT8 after the Vosk Georgian wake gate.
- Added regression coverage for the observed Steam transcription failure.

## Earlier versions

Earlier development history is summarized in `project_plan.md` and
`UPGRADE_PLAN.md`; it predates the public repository changelog.
