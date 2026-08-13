# micro:bit V2 Expansion Plan

## Objective

Use the existing micro:bit V2 immediately as a safe physical GELA controller,
then evolve the same protocol toward joystick, robot, and room-distance voice
hardware. The Windows PC remains the command authority and Georgian ASR host.

## Hardware facts and consequences

The micro:bit V2 has an nRF52833 processor, 128 KB RAM, 512 KB flash, BLE 5,
USB serial, a microphone, speaker, buttons, 5x5 LEDs, touch logo, accelerometer,
compass, radio, GPIO, and battery input. It has no Wi-Fi. Its standard microphone
APIs expose sound level/events; high-quality continuous speech transport would
require low-level PDM/audio firmware and remains constrained by memory,
throughput, microphone placement, and radio power.

Therefore:

- It can be an excellent control/status/sensor/robot board.
- It cannot run GELA's 365 MB Georgian ASR model.
- BLE is suitable for commands and status, not the preferred path for continuous
  speech audio.
- The microphone should first be used for clap/noise/activity events and carefully
  measured experiments—not advertised as a finished remote voice microphone.

## Stable protocol first

Define messages independent of USB, BLE, or Wi-Fi. Example events:

```text
HELLO protocol=1 device=microbit-v2 capabilities=buttons,display,motion,sound
EVENT id=42 type=button.a
EVENT id=43 type=gesture.shake
EVENT id=44 type=sound.loud value=183
ACK id=42 result=ok
STATE assistant=listening
STATE action=success
```

Every event has an ID; the host acknowledges it once. Unknown, duplicated,
oversized, malformed, or unauthenticated events are rejected. There is no
arbitrary command or shell message.

## Phase 1 — identify and baseline the board

- Confirm V2 visually and through firmware.
- Record firmware/runtime version and USB serial identity.
- Test buttons, logo, LEDs, speaker, microphone level, accelerometer, compass,
  battery operation, and serial reliability.
- Measure event latency and reconnect behaviour.

Exit gate: a reproducible diagnostic firmware image and results table.

## Phase 2 — wired GELA controller

- Implement USB serial framing and reconnect logic.
- Map A, B, A+B, logo, shake, and tilt to configurable GELA intents.
- Display sleeping, listening, processing, success, failure, disconnected, and
  muted states on the LED matrix.
- Use tones only for local feedback; retain recorded Georgian responses on PC.
- Add a tray settings page for enabling the device and changing mappings.

Exit gate: no event can bypass GELA's allowlist, and unplug/reconnect is safe.

## Phase 3 — joystick and accessibility controls

- Attach a joystick through GPIO/analogue inputs or a supported edge-connector
  breakout.
- Add dead-zone, debounce, long-press, repeat-rate, and calibration settings.
- Keep joystick events semantic (`joystick.left`, `joystick.press`) so the same
  firmware can control menus, volume, windows, or a robot profile.

Exit gate: stable input without drift or accidental repeated destructive actions.

## Phase 4 — BLE remote

- Pair to Windows using BLE and expose only the versioned GELA service.
- Add device identity, session nonce, sequence numbers, acknowledgements, and
  rate limits.
- Retain USB as recovery/configuration transport.
- Measure range, latency, battery life, reconnects, and coexistence with Windows
  Bluetooth control commands.

Exit gate: authenticated command/status control across the intended room.

Important: if GELA switches off Windows Bluetooth, BLE control disconnects and
cannot switch it back on. USB or another independent transport is required for
recovery.

## Phase 5 — microphone experiments

### Built-in microphone uses that are realistic

- Sound-level telemetry.
- Clap or loud-event shortcuts with cooldown and confirmation.
- Robot collision/distress/noise detection.
- Push-to-talk indicator and capture trigger for a separate audio device.

### Experimental raw audio

- Develop native nRF52833 firmware to access the PDM microphone.
- Test 16 kHz, mono, 16-bit capture, buffering, packet loss, and host reconstruction
  over USB first.
- Compare recognition accuracy against the current USB microphone using a fixed
  Georgian command corpus.
- Do not proceed to wireless audio unless measured accuracy and latency are useful.

This experiment may prove that the built-in microphone is unsuitable for ASR;
that is an acceptable, documented result.

## Phase 6 — Wi-Fi voice satellite

Wi-Fi cannot be added to the nRF52833 by firmware. Add a separate coprocessor:

- Preferred: ESP32-S3 voice board with PSRAM and an I2S microphone or two-mic
  audio front end.
- Better far-field option: ReSpeaker Lite/XIAO ESP32-S3.
- Connect the micro:bit and ESP32-S3 by UART or I2C; micro:bit handles sensors,
  joystick, LEDs, and robot safety while ESP32-S3 handles Wi-Fi/audio transport.
- Stream wake-gated or push-to-talk PCM to the Windows GELA host over the local
  network; the PC performs Georgian ASR and returns response/state events.

Do not use an ESP8266 for this role: its audio, memory, and development margins
are unnecessarily restrictive.

Exit gate: authenticated local-network audio, bounded buffering, packet-loss
handling, and no cloud dependency.

## Phase 7 — mini robot

- Keep motor control local to the micro:bit with a compatible motor driver and
  separate motor power supply.
- Add physical and software emergency stop, command timeout, speed/acceleration
  limits, low-battery behaviour, and disconnect-to-stop.
- GELA sends bounded goals (`forward`, `left`, `stop`) rather than raw pin values.
- Sensor avoidance and emergency stop override all remote commands.
- Never connect motors directly to micro:bit GPIO or power them from its 3 V pin.

Exit gate: the robot stops safely on reset, disconnect, malformed input, timeout,
or loss of host power.

## Recommended purchase order

1. Nothing: start with the micro:bit, USB cable, and current PC.
2. Edge-connector breakout and joystick.
3. Robot chassis with a micro:bit-compatible motor driver and proper battery pack.
4. ESP32-S3 audio/Wi-Fi board only after the wired protocol is stable.
5. Better microphone/audio front end if raw micro:bit microphone testing fails.

This order prevents buying wireless/audio hardware before the protocol and robot
safety model are proven.
