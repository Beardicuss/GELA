# GELA Roadmap

The roadmap records direction, not a promise of dates. Reliability and safe
Windows control take priority over adding conversational features.

## Current desktop foundation

- Offline Georgian wake-gated short commands.
- Windows application and game lifecycle control.
- Audio, radio, volume, window, catalog, aliases, diagnostics, tray UI, and
  installer support.

## Companion devices

- Continue physical stability testing of the mPython Board 3.0 Wi-Fi terminal.
- Keep its interface intentionally small: push-to-talk, mute, face states, and
  ambient personality.
- Preserve Android local-Wi-Fi operation while improving private remote access
  and view-only screen efficiency.
- Add no board feature unless it survives repeated command, reconnect, and
  power-cycle testing without weakening the restricted host API.

Implementation details and safety decisions are recorded in
`mcu/mpython_board_3_face/SMART_TERMINAL_PLAN.md`.

## Deferred

- Conversational AI and code generation are outside GELA's purpose.
- Voice-based Windows authentication is not planned without a security design
  that is stronger than a spoken secret.
