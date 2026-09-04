# Changelog

All notable changes are recorded here. Versions follow semantic versioning where
practical.

## Unreleased

- Added password-protected Gela recovery backups on disk D with authenticated
  AES-256-GCM encryption, Scrypt password derivation, integrity verification,
  strict restore allowlisting, and a tray-accessible recovery window.
- Hardened the mPython Board Wi-Fi bridge with protocol/capability negotiation,
  authenticated structured lifecycle events, bounded event payloads, clearer
  failure states, and exponential reconnect/discovery backoff.
- Hardened the board's USB protocol tester against the ESP32-S3 reset that can
  occur when Windows opens its serial port.
- Replaced fixed four-second board recording with hold-A/release-to-send smart
  push-to-talk, a 300 ms minimum, 250 ms release tail, and reliable five-second
  hardware cap. Upload and recognition run outside the animation loop so the
  face stays responsive while Gela processes the command.
- Added an MCU PC-health card opened by holding touch N. It shows cached CPU,
  RAM, system-disk free space, network, and battery/charging state for 10 seconds
  before returning to the animated face.
- Added smart board/mobile command feedback and an N-tap activity card showing
  the current Gela state, recognized command, matched target, result, and source.
  Georgian transcripts are transliterated for the board's embedded Latin font.
- Removed the experimental board-speaker response path after physical testing
  exposed repeatable vendor-firmware crashes. PC response playback remains active.

### Changed

- Replaced the Georgian standby command with `დაიძინე`, including tolerance
  for the speech recognizer's spaced `დაი ძინე` transcript.
- Fixed standby on Windows by explicitly enabling `SeShutdownPrivilege`, using
  the correct one-byte Win32 return type, and trusting the exact embedded
  wake-command result over corrupted mixed-script retranscription.
- Run the final standby transition in a delayed helper process so mobile and
  voice command threads can finish cleanly, with a dedicated failure log.
- Fall back to Windows `SetSystemPowerState` when Modern Standby firmware
  rejects `SetSuspendState` with `ERROR_NOT_SUPPORTED`.
- On S0-only Modern Standby systems that reject both suspend APIs, lock the
  interactive session and switch off the display to trigger Modern Standby.

### Added

- Automatic USB discovery and reconnecting state bridge for the ESP32-S3
  mPython Board 3.0 Gela face, using an allowlisted six-state serial protocol.
- Board face reactions for Gela listening, processing, speech, successful
  execution, failures, and idle operation.
- Restored automatic allowlisted playlist/media catalog discovery, with both
  `ჩართე` and `დაუკარი` commands and persistent Georgian aliases such as
  `ქრონიკები` and `ინსაიტი`.
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
