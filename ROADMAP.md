# GELA Roadmap

The roadmap records direction, not a promise of dates. Reliability and safe
Windows control take priority over adding conversational features.

## Current desktop foundation

- Offline Georgian wake-gated short commands.
- Windows application and game lifecycle control.
- Audio, radio, volume, window, catalog, aliases, diagnostics, tray UI, and
  installer support.

## Hardware expansion

1. Define a versioned, transport-neutral peripheral protocol.
2. Build a micro:bit V2 USB controller/status prototype.
3. Add joystick input without changing the host command contract.
4. Evaluate BLE for low-bandwidth buttons, status, and telemetry.
5. Evaluate an external Wi-Fi/audio coprocessor as a GELA voice satellite.
6. Add a robot profile with local emergency stop and bounded motor commands.

The detailed hardware decisions and safety gates are in
`docs/MICROBIT_ROADMAP.md`.

## Deferred

- Conversational AI and code generation are outside GELA's purpose.
- Voice-based Windows authentication is not planned without a security design
  that is stronger than a spoken secret.
