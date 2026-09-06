# Gela Face — mPython Board 3.0

Animated Gela face and optional remote input for the ESP32-S3-based mPython
Board 3.0. It supplements the normal PC microphone; it does not replace it.

The working controls are:

- **Press and release A:** then speak during the four-second capture
- **A+B:** toggle Windows mute
- **Status strip:** Wi-Fi strength, PC/Gela state, and recent mobile activity
- **Ambient personality:** while Gela is idle, the face becomes attentive, calm,
  sleepy, or away according to recent PC input; command states always take priority

USB remains supported for face-state control and maintenance. Wi-Fi uses a
separate random board token and can access only status, command
audio, cancel, and mute—not mobile files, clipboard, screen, or device-management
APIs. Board-speaker responses are intentionally disabled: repeated playback tests
proved unstable in the vendor firmware, while PC response audio remains reliable.

To provision Wi-Fi, exit Gela so the serial port is free, then run:

```powershell
.\.venv\Scripts\python.exe .\mcu\mpython_board_3_face\tools\provision_wifi.py
```

The password prompt is hidden and the password is stored only in the board's
local configuration.

## Hardware assumptions

- Board: mPython/掌控板 3.0
- Display: built-in 1.47-inch ST7789, 320×172
- Firmware detected on the physical board: MicroPython 1.24.1,
  `mpython pro with ESP32S3`, providing the LVGL-based `lv_oled` wrapper

The detected firmware's direct RGB565 LVGL canvas path crashes inside its
native display binding. The supported `lv_oled.Bitmap()` PNG path is therefore
used for reliable animation. Do not install a generic ST7789 driver.

## Build the frames

From the repository root:

```powershell
python .\mcu\mpython_board_3_face\tools\convert_frames.py `
  "C:\Users\DanTe\Downloads\gela_assets_wepb" `
  ".\mcu\mpython_board_3_face\build\frames"
```

The converter uses one shared content crop for stable alignment and composites
alpha onto black. It writes 320×172 RGB565 diagnostic files, lossless previews,
and 256-color board PNGs. The compact board PNGs fit the firmware's limited
filesystem and are deployed through its supported LVGL decoder.

The verified active PNG set is checked into `assets/board_frames`, so a fresh
repository checkout can restore the working board without the ignored local
`build` directory. Copy newly approved conversions there before a checkpoint.

## Verify and deploy

1. Connect the board with a USB data cable and note its COM port.
2. Run `firmware/display_test.py` first. It should show `GELA DISPLAY OK`.
3. If the colors are correct, install `mpremote` and deploy:

```powershell
python -m pip install mpremote
.\mcu\mpython_board_3_face\deploy.ps1 -Port COM5
```

Deployment copies the 15 `.png` files into `/gela_frames` and installs the
standalone `main.py`. Resetting the board starts the natural idle animation.
Listening, thinking, talking, success, and error remain available as explicit
runtime states for later Gela integration; they are not played in an automatic
sequence.

The attentive idle rhythm is center → left → center → right. Its irregular,
180 ms blink is allowed only from the centered frame, preventing visible pose
jumps. Calm reuses that blink only from its centered `calm_0` pose. The older
downward idle frame is intentionally not installed.

The ambient layer is intentionally lightweight. Windows reports only a coarse
mood string (`ATTENTIVE`, `CALM`, `SLEEPY`, or `AWAY`); the board changes the
existing idle animation's pace and blink pattern. Calm combines one dedicated
middle frame with the existing left/right idle frames; sleepy and away each use
one dedicated optimized frame. No sensor history, application
content, extra screen, audio task, or board thread is involved.

Ambient timing is attentive for the first minute without PC input, calm from one
to five minutes, sleepy from five to seven minutes, and away/sleeping afterward.

The runtime reads one compressed PNG at a time through the firmware's supported
LVGL wrapper and starts a fresh draw layer after every swap.
`FaceAnimator.last_blit_ms` records the most recent decode, draw, and display
time for the later performance pass.

## Gela USB protocol

Gela discovers the board by its stable Espressif USB identity (`303A:1001`),
so the COM number may change without requiring configuration. Messages are
newline-delimited ASCII and only six states are accepted:

```text
GELA1 STATE IDLE
GELA1 STATE LISTEN
GELA1 STATE THINK
GELA1 STATE TALK
GELA1 STATE SUCCESS
GELA1 STATE ERROR
```

The board acknowledges valid messages with `GELA1 OK STATE <state>`. Invalid
input cannot execute Python or arbitrary board operations. Gela reconnects
automatically after unplug/replug.
