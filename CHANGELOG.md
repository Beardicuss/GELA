# Changelog

All notable changes are recorded here. Versions follow semantic versioning where
practical.

## 1.6.0 - 2026-08-14

### Added

- Georgian Settings microphone dropdown populated from microphones currently detected by Windows.
- Manual refresh action and clear status when a previously saved microphone is disconnected.

### Changed

- Hidden driver pins and duplicate backend aliases are excluded from the microphone list.
- Removed the unused micro:bit roadmap and placeholder directories.

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
