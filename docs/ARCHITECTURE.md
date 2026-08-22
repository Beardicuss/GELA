# Architecture

GELA is an offline-first Windows controller. Vosk continuously performs the
lightweight Georgian wake gate. Only after the wake phrase is accepted does the
larger Omnilingual ASR model transcribe a bounded command utterance. Parsed
commands resolve through fixed system intents or an allowlisted application
catalog before Windows actions run.

```text
Microphone -> VAD -> Vosk wake gate -> Omnilingual command ASR
                                      -> intent/catalog resolution
                                      -> allowlisted Windows action
                                      -> verification -> recorded response
```

Authenticated mobile push-to-talk audio enters through a bounded PCM endpoint
and is queued onto the same worker thread, reusing the loaded Omnilingual model.
Transcription and execution remain separate: the phone receives a transcript,
then submits it through the normal allowlisted text-command endpoint.

The bridge owns a stable random identity under `%LOCALAPPDATA%\Gela\mobile` and
answers a fixed UDP discovery probe on port `8766`. Responses contain only the
bridge identity, PC name, and current HTTP port; authentication remains required
for status, transcription, and commands on port `8765`.

Because the UDP identity is public, a relocated phone first requests a bounded
one-time proof derived from its stored token digest, a fresh nonce, and the
phone's observed source address. The phone verifies that proof before sending an
Authorization header to the new address, preventing simple bridge-ID spoofing.

Optional different-network access is implemented with a Tailscale private HTTPS
Serve endpoint targeting `127.0.0.1:8765`. The bridge reports the resulting URL
through pairing and authenticated status metadata, while bearer-token checks
remain unchanged. Local HTTP and authenticated UDP rediscovery remain available
on the LAN. Gela never configures public Funnel exposure or router forwarding.

Screen sharing adds a stricter boundary: the frame endpoint requires a paired
token, an unexpired permission granted through biometric mobile authorization
or the PC fallback, and a loopback proxy source. Direct LAN
clients therefore cannot retrieve screen content over cleartext HTTP. Pillow
captures the Windows desktop only on demand, scales it within 1280×720, returns
a `no-store` JPEG, and serializes capture work. Per-device limiting caps frame
requests, and no remote input endpoint exists.

Authenticated mobile transfer endpoints expose only explicit clipboard actions
and two fixed folders under `%LOCALAPPDATA%\Gela\mobile\transfers`. Phone uploads
are written without execution to `inbox`; phone downloads can read only regular
files deliberately placed in `outbox`. Filenames are sanitized, traversal is
rejected, and individual files are capped at 25 MB.

Paired mobile credentials are stored as SHA-256 digests. Authenticated devices
can request a redacted device inventory, rotate only their own token, and revoke
a selected device. Rotation retains the previous digest for no more than five
minutes until the phone confirms it safely persisted the replacement. A separate
200-event audit records only timestamps, event types, and opaque device IDs.

The system-tray process owns lifecycle and UI. Personal settings, generated
catalogs, learned process targets, runtime state, and logs live under
`%LOCALAPPDATA%\Gela`; application defaults ship beside the executable.

## Hardware boundary

External controllers must send semantic events such as `button.a` or
`volume.delta`, never shell commands. The Windows host remains authoritative: it
authenticates the device, maps events to allowed intents, executes actions, and
returns a small status event. This boundary supports USB, BLE, Wi-Fi, joystick,
and robot transports without duplicating command execution logic.

## Repository layout

- `src/voice_assistant/`: desktop application and command engine.
- `tests/`: automated desktop regression suite.
- `config/`: distributable default configuration; generated personal catalogs
  are ignored.
- `audio/voice/`: recorded Georgian responses and their manifest.
- `scripts/`: development, model, voice, build, signing, and release tooling.
- `installer/`: Inno Setup package definition.
- `docs/`: architecture and hardware plans.
- `microbit/`: reserved for future board source and generated-output placeholders.
