# Gela Board Smart Terminal — Implementation Plan

## Goal and non-negotiables

Turn the mPython Board 3.0 into a useful optional Gela terminal while preserving
the normal PC USB microphone and Gela Mobile. The face remains the primary UI;
small overlays appear only when useful. Existing USB control remains a fallback.

- Board actions use the existing restricted board token and allowlisted API.
- No arbitrary command execution, screen/file/clipboard access, or exposed secrets.
- No automatic PC lock based only on weak light/motion evidence.
- Every feature must work on Wi-Fi power with no PC USB connection.
- Changes are tested and installed locally, but committed only after user approval.

## Phase 0 — Baseline and protocol hardening (implemented)

1. Back up the working board firmware and configuration (excluding credentials
   from Git and logs).
2. Add protocol capabilities/version negotiation and structured board events.
3. Add reconnect backoff, bounded request sizes, timeouts, and clearer states:
   `WIFI OFF`, `PC OFFLINE`, `AUTH ERROR`, `GELA PAUSED`, and `READY`.
4. Add PC-side structured logging without recording or retaining microphone audio.
5. Regression-test current A, B, A+B, USB face states, Wi-Fi discovery, mobile
   commands, and PC microphone input.

Acceptance: all existing behavior survives disconnects, PC restarts, DHCP address
changes, and board power cycles.

Implementation checkpoint: protocol v2 advertises explicit capabilities while
remaining compatible with v1, board event bodies are authenticated and bounded,
and reconnect attempts use capped exponential backoff plus rediscovery. Automated
tests pass, the installed PC bridge recovered after a forced restart, and the
physical board recovered after reset at `192.168.100.7`. A real router-assigned
address change remains a field check the next time DHCP changes the PC address.

## Phase 1 — Smart push-to-talk (implemented and physically verified)

Target interaction: hold A, speak, release A, then send. Minimum duration 300 ms;
maximum duration 15 seconds; visible recording/progress state; release never clips
the last syllable (about 250 ms tail).

The board's convenient `audio.record()` API is fixed-duration and blocking, so
implementation begins with a hardware spike:

1. Test whether its recorder can be stopped safely from a second MicroPython
   thread when A is released.
2. If not, use bounded ADC/I2S chunk capture into PSRAM with a reusable buffer.
3. Stream chunks to the PC when possible; use a bounded temporary WAV only as a
   fallback and always delete it afterward.
4. Apply board-specific DC removal, conservative gain normalization, and optional
   resampling before Omnilingual ASR.
5. Keep exact/unique allowlist correction; ambiguous recognition must fail safely.

Acceptance: short and long Georgian commands are not clipped, releasing A sends
once, silence is rejected, and the PC microphone keeps operating simultaneously.

## Phase 2 — Spoken responses on the board (deferred after hardware test)

The board's local speaker works in isolated tests, but network-response playback
repeatedly crashed/restarted the vendor firmware and could leave the board unable
to boot until recovery. The response endpoint and playback code were removed.
PC response audio remains the safe default; revisit only with different firmware
or a proven streaming/audio driver.

1. Add a board/PC output preference: PC, board, or both; default to PC so current
   behavior is unchanged.
2. Start with Gela's existing fixed response sounds (`ready`, success, error,
   cancelled), delivered through an authenticated, single-use audio URL.
3. Add generated answer playback later only if response encoding and latency fit
   the board reliably.
4. Cache only small fixed sounds; cap download size and remove temporary audio.
5. B immediately stops board and PC playback.

Acceptance: audio never plays on the wrong device, temporary URLs expire, and a
network failure falls back cleanly to the configured PC response.

## Phase 3 — Privacy mode

1. Long-press B (2 seconds) toggles global Gela privacy mode. Short B remains
   cancel/stop.
2. Privacy mode pauses PC microphone processing and rejects board/mobile audio.
3. Show a persistent `MIC OFF` symbol and red LED pattern; no animation may imply
   listening while privacy is active.
4. Require another long B press or the tray control to resume; persist the choice
   across reconnects but define reboot behavior explicitly in settings.

Acceptance: PC, mobile, and board audio are all rejected while private, while
non-audio status/health features remain available.

## Phase 4 — Media controller

Initial touch mapping:

- P: previous track
- Y: play/pause
- T: next track
- H: volume down
- O: volume up
- N: show now playing

Actions use existing Windows media-key functions. Add optional Windows media
session integration for title/artist and playback state; if metadata is unavailable,
show only the action result. Debounce touch input and rate-limit volume changes.

Acceptance: accidental touches do not repeat, media controls work while Gela is
listening, and the face returns after the temporary now-playing card.

## Phase 5 — PC health monitor (removed after physical stability testing)

1. Add a small cached PC metrics service: CPU, memory, disk-free percentage,
   network state, and laptop battery where available.
2. GPU load/temperature is optional: use vendor-supported data when installed and
   display `N/A` otherwise—never fail the entire monitor.
3. A compact temporary health card was evaluated on touch N.
4. Add threshold notifications for low disk, high temperature, and low battery,
   with hysteresis/cooldowns to prevent repeated alerts.

Acceptance: polling is lightweight, unavailable sensors are handled honestly, and
values do not block voice or animation traffic.

Physical testing found repeatable native board resets after adding the N health and
activity dashboards. Both features and their status payloads were removed, and the
firmware was restored to the compact, previously stable single-threaded command
path. Reliability takes precedence over optional board telemetry.

## Phase 6 — Notification display

Deliver notifications in two levels:

1. Reliable first: Gela-owned events—command results, download completion, mobile
   connection, PC battery/disk warnings, reconnects, and scheduled Gela reminders.
2. Optional later: selected Windows/app notifications, only through supported
   permissioned APIs or explicit per-app integrations. Do not scrape private toast
   contents globally by default.

Cards are priority-queued, deduplicated, privacy-filtered, limited in length, and
auto-dismissed before returning to the face. B dismisses the current card.

Acceptance: no notification floods, secrets/message contents are hidden by default,
and critical connection/privacy alerts outrank informational cards.

## Phase 7 — Offline emergency controls

1. Store only the PC's selected Wake-on-LAN MAC and last-known network details.
2. When the PC is offline, A offers/sends a WOL magic packet instead of recording.
3. Show diagnostics: Wi-Fi association, IP, signal quality, discovery result, last
   successful contact, and likely failure category.
4. Retry discovery with bounded exponential backoff.
5. Document that WOL depends on PC firmware/NIC/router support and is usually most
   reliable over Ethernet; never claim success until the PC responds.

Acceptance: offline mode never loses configuration, WOL packets remain local, and
the display distinguishes `WAKE SENT`, `WAKING`, and `STILL OFFLINE`.

## Phase 8 — Ambient Gela personality

Presence automation was rejected because the built-in light/motion sensors cannot
reliably prove that a person is present. The safer ambient feature changes character,
not PC behavior:

1. Windows input-idle time is reduced to one coarse mood: attentive, calm, sleepy,
   or away.
2. The board reuses its existing idle frames with different pace and blink patterns.
3. Listening, thinking, success, and error states always override the ambient mood.
4. No occupancy claim, automatic lock/pause, sensor logging, extra controls, audio
   thread, or heavy rendering is added.

Acceptance: ambient animation cannot execute actions and failure to read Windows
idle time leaves the last safe mood in place without affecting Gela.

## Delivery order

1. Encrypted recovery backups to disk D (off-device; suitable for Drive upload)
2. Baseline/protocol hardening
3. Smart push-to-talk
4. Privacy mode
5. Media controller
6. Board spoken responses
7. Health monitor
8. Gela-owned notifications
9. Offline/WOL controls
10. Lightweight ambient personality
11. Optional Windows/app notifications and richer spoken answers

Each phase ends with unit tests, physical-board tests, Wi-Fi-only testing from a
charger, PC/mobile regression testing, and a user checkpoint before the next phase.

## Recovery checkpoint — encrypted off-device backup

Before the feature phases, add a versioned `.gelabackup` archive stored under
`D:\Gela Backups`. It contains personal settings, aliases, routines, mobile pairing
identities, and the MCU authentication token. It excludes logs, models, generated
catalog/audit/runtime data, screen captures, and the board's Wi-Fi password.

The archive uses password-derived AES-256-GCM authenticated encryption, records a
SHA-256 manifest, restores only an explicit path allowlist, and never stores the
password. The user can copy the encrypted file to Google Drive for an off-site copy.
