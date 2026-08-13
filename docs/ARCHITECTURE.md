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
