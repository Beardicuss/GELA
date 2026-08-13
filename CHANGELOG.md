# Changelog

All notable changes are recorded here. Versions follow semantic versioning where
practical.

## Unreleased

### Planned

- micro:bit V2 USB controller and status prototype.
- Transport-neutral peripheral protocol for future wireless and robot devices.

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
