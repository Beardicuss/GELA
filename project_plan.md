---

# Architecture Plan: Vosk-Powered Offline Voice Launcher for Windows

## System Architecture Overview

The system operates as an ultra-lightweight, offline **Two-Stage State Machine**:

```text
[STATE 1: SLEEPING / WAKE-WORD DETECTOR]
       │  (Continuous low-power audio streaming ~0.5% CPU)
       ▼
[Wake Word Triggered!]
       │
       ▼
[STATE 2: VOSK GRAMMAR-RESTRICTED RECOGNITION]
       │  (Listens for 3-second window using pre-loaded Vosk model)
       ▼
[Command String Matching]
       │  (Matches exact recognized phrase against Windows executable paths)
       ▼
[Windows OS Execution]
       │  (Launches target .exe file via system call)
       ▼
[Return to STATE 1: SLEEPING]

```

---

## Phase 1: Environment & Audio Pipeline Setup

1. **Environment Setup**
* Prepare an isolated Python environment.
* Install lightweight sound-capturing dependencies (`PyAudio` or `sounddevice`).


2. **Vosk Offline Models Configuration**
* Download small, lightweight Vosk language models (~40–50 MB each) for target languages (English and Georgian).
* Store model files locally in the project directory for 100% offline access.



---

## Phase 2: Lightweight Wake-Word Detection ("Sleeping State")

1. **Low-Resource Engine Integration**
* Integrate an efficient wake-word engine (such as *openwakeword* or Vosk’s built-in keyword spotter).
* Keep the background loop listening continuously to the microphone stream with near-zero CPU and RAM utilization (~30–40 MB RAM).


2. **Activation Sensitivity**
* Set activation thresholds to eliminate false positives from ambient room sound or music.



---

## Phase 3: Vosk Command Processing (Grammar Mode)

1. **Grammar Restriction Setup**
* Configure Vosk using its **Restricted Grammar JSON feature**.
* Instead of searching an entire dictionary, force Vosk to only listen for your exact list of trigger phrases (e.g., `["open steam", "open chrome", "გახსენი სთიმი"]`).
* *Benefit:* Eliminates misinterpretation, drastically reduces processing time to under 0.1 seconds, and uses almost no RAM.


2. **Audio Window Processing**
* Upon wake-word activation, pass the recorded 3-second audio buffer directly to the Vosk recognizer.
* Obtain the clean JSON output string returned by Vosk.



---

## Phase 4: Command Mapping & Windows Execution

1. **Configuration File Mapping**
* Maintain an offline mapping file (JSON or YAML) associating text phrases directly with system paths.
* **Mapping Logic:**
* `phrase` $\rightarrow$ `C:\Path\To\Program.exe`




2. **Execution Engine**
* Match the output from Vosk against the mapped key-value pairs.
* Execute the application using native Windows process handlers.
* Immediately flush audio buffers to prevent re-triggering, and return the system to **State 1 (Sleeping)**.



---

## Phase 5: Windows Deployment & Auto-Start

1. **Headless Execution**
* Wrap the execution script to run silently in the background without spawning an active command prompt window.


2. **Startup Integration**
* Create a Windows shortcut for the background worker.
* Place the shortcut into the Windows `Shell:Startup` folder to ensure automatic launch whenever the PC boots up.



---Analyze the plan and create a skills for this project creation.
---Folder is empty we are starting from zero.
---Phase 2: replace windows password/pincode entering via voice unlock by secret word (by microphone: Microphone 2- USB Microphone Default device)

---

## Current Reliability Upgrade Roadmap

1. **State-aware action verification — completed**
   * Verify a stable application/game process or window before reporting launch success.
   * Allow longer bounded startup for Steam and anti-cheat.
   * Verify known or window-discovered processes exited after complete-close commands.
2. **Current-state awareness — completed**
   * Report already-running, already-stopped, and already-configured states.
3. **General mixed-language window commands — completed**
   * Extend Georgian verb + registered English target handling to focus, minimize, maximize, and restore.
4. **Automatic process learning — completed**
   * Observe and persist the process/window created by an application launch.
5. **Advanced game lifecycle handling — completed**
   * Track launcher, anti-cheat, and real game processes separately.
6. **Optional one-sentence wake commands — completed**
   * Support `გელა გახსენი ქრომი` while preserving two-stage mode.
   * Join early decoder endpoint segments through the true end of the utterance and normalize formal Georgian verbs.
7. **Recognition testing window — completed**
   * Show Georgian/English decoder results and safely promote a result to an alias.
8. **Per-application control profiles — completed**
   * Configure preferred processes, titles, aliases, and close behavior.

---

## Audit Remediation Roadmap

1. **Background-noise adaptation — completed**
   * Learn sustained ambient noise without decoding it continuously as speech.
   * Preserve recognition of a real voice above the learned noise floor.
   * Allow calibration to recommend thresholds above the previous 500-RMS ceiling.
2. **Packaged vocabulary validation — completed**
   * Validate aliases with Vosk's direct model vocabulary lookup.
   * Avoid native stderr parsing so validation works in the console-free executable.
3. **Duplicate catalog identity resolution — completed**
   * Give same-named targets stable descriptive qualifiers during every catalog scan.
   * Preserve complete dotted executable names for launch verification and close actions.
4. **Voice-readiness catalog status — completed**
   * Classify every detected target as Georgian-ready, English-ready, bilingual, invalid, or unconfigured.
   * Show the results in a searchable Georgian catalog window instead of raw JSON.
5. **Development and installed-data synchronization — completed**
   * Use a regular Python 3.11–3.13 environment that reads the real `%LOCALAPPDATA%\Gela` data root.
   * Reject Microsoft Store Python development runtimes that silently redirect Gela data into a package cache.
   * Verify source and installed Gela share settings, aliases, profiles, routines, logs, and the complete application catalog.
6. **Stale aliases and package metadata cleanup — completed**
   * Move aliases for absent applications into a reversible archive instead of deleting personal voice names.
   * Restore archived aliases automatically when the exact catalog application returns, while preserving conflict safety.
   * Remove generated source package metadata after environment setup and release tests.
7. **Voice-response format normalization — completed**
   * Preserve all original uncompressed recordings separately from processed playback assets.
   * Normalize every response to loudness-controlled 48 kHz mono 16-bit PCM through a manifest-driven FFmpeg pipeline.
   * Reject missing, orphaned, unreadable, or incompatible response files during release builds and voice-status checks.
8. **Release code signing — certificate required**
   * Sign and verify the application before portable packaging, then sign and verify the completed installer.
   * Require SHA-256 Authenticode, RFC 3161 timestamping, exact certificate selection, Code Signing EKU, and the Softcurse Systems publisher subject.
   * Block signed-release mode until a trusted Softcurse Systems certificate with an accessible private key is supplied.
