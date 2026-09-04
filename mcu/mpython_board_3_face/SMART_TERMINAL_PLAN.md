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

## Phase 0 — Baseline and protocol hardening

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

## Phase 1 — Smart push-to-talk

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

## Phase 2 — Spoken responses on the board

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

## Phase 5 — PC health monitor

1. Add a small cached PC metrics service: CPU, memory, disk-free percentage,
   network state, and laptop battery where available.
2. GPU load/temperature is optional: use vendor-supported data when installed and
   display `N/A` otherwise—never fail the entire monitor.
3. Open the health card with a deliberate gesture (proposed: hold N for one second)
   and rotate pages; do not permanently clutter the face.
4. Add threshold notifications for low disk, high temperature, and low battery,
   with hysteresis/cooldowns to prevent repeated alerts.

Acceptance: polling is lightweight, unavailable sensors are handled honestly, and
values do not block voice or animation traffic.

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

## Phase 8 — Presence automation (conservative rollout)

The board has light and motion sensors, not a true human-presence sensor. Therefore:

1. Begin in observe-only mode and log no raw sensor history—only bounded local
   confidence state.
2. Fuse recent board movement, light changes, PC input-idle time, time of day, and
   optional phone presence. Any single sensor is insufficient.
3. First automation: pause listening after a configurable confident absence and
   resume on return.
4. PC locking remains opt-in and requires a warning/grace period with an easy cancel.
5. Recommend an inexpensive PIR/mmWave sensor later if reliable occupancy is wanted.

Acceptance: false absence never immediately locks the PC; privacy and manual pause
always override presence automation.

## Delivery order

1. Baseline/protocol hardening
2. Smart push-to-talk
3. Privacy mode
4. Media controller
5. Board spoken responses
6. Health monitor
7. Gela-owned notifications
8. Offline/WOL controls
9. Presence observe-only mode, then opt-in automation
10. Optional Windows/app notifications and richer spoken answers

Each phase ends with unit tests, physical-board tests, Wi-Fi-only testing from a
charger, PC/mobile regression testing, and a user checkpoint before the next phase.
