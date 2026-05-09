# Roadmap: meetcap

## Overview

Milestone 1 delivers a working audio capture tool. Three phases build on each other: first the project shell and config system, then platform-specific audio backends (the highest-risk work), then the recording pipeline that mixes those backends into a clean WAV file. When all three phases are done, `meetcap` starts capturing audio on both macOS and Windows and produces a valid WAV on Ctrl+C.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Project scaffolding, click entrypoint, TOML config, first-run wizard
- [ ] **Phase 2: Platform Backends** - macOS ScreenCaptureKit spike and Windows WASAPI loopback backend
- [ ] **Phase 3: Recording Pipeline** - Dual-stream mixer, resampling, Ctrl+C handling, WAV output

## Phase Details

### Phase 1: Foundation
**Goal**: The project installs cleanly and the CLI entrypoint works with a config system ready to store settings
**Depends on**: Nothing (first phase)
**Requirements**: CLI-01, CLI-02, CLI-03
**Success Criteria** (what must be TRUE):
  1. `pipx install .` (or `uv pip install -e .`) succeeds and `meetcap --help` prints usage
  2. Running `meetcap` with no existing config prompts the user for a recordings directory and writes it to a TOML file at the platform-appropriate path
  3. Running `meetcap` again with config present skips the prompt and proceeds to recording mode (even if recording itself is a stub)
  4. Config file is readable TOML containing `recordings_dir` at the correct OS-specific path
**Plans**: TBD

Plans:
- [ ] 01-01: uv project setup, package structure, click entrypoint, `meetcap`/`meetcap "<title>"` commands
- [ ] 01-02: TOML config system with platformdirs, first-run wizard for recordings_dir

### Phase 2: Platform Backends
**Goal**: System audio can be captured on both macOS (ScreenCaptureKit) and Windows (WASAPI loopback) through a shared backend interface
**Depends on**: Phase 1
**Requirements**: AUD-03, AUD-04
**Success Criteria** (what must be TRUE):
  1. On macOS 13+, system audio samples are received in a callback without crashing — including on macOS 15 (SCStream delegate not garbage-collected)
  2. On macOS, missing Screen Recording permission produces a clear, actionable error message rather than a silent failure
  3. On Windows 10+, WASAPI loopback captures system audio samples via PyAudioWPatch without requiring any driver installation
  4. Both backends conform to the same `SystemAudioBackend` protocol and can be swapped by platform detection
**Plans**: TBD

Plans:
- [ ] 02-01: `SystemAudioBackend` protocol, macOS ScreenCaptureKit backend with delegate retain fix and permission check
- [ ] 02-02: Windows WASAPI loopback backend via PyAudioWPatch

### Phase 3: Recording Pipeline
**Goal**: Users can record mic + system audio simultaneously into a valid WAV file that stops cleanly on Ctrl+C
**Depends on**: Phase 2
**Requirements**: AUD-01, AUD-02, AUD-05
**Success Criteria** (what must be TRUE):
  1. Running `meetcap` starts recording and prints a confirmation message showing mic and system audio are both active
  2. Both streams are resampled to 48000 Hz canonical rate before mixing — no audible drift between mic and system audio
  3. Pressing Ctrl+C stops recording, flushes all buffers, and writes a valid WAV file (verified with `soundfile.info()`)
  4. The output WAV file is saved to the configured recordings directory with a timestamped filename
**Plans**: TBD

Plans:
- [ ] 03-01: Dual-stream mixer with samplerate resampling to 48000 Hz canonical rate
- [ ] 03-02: Ctrl+C signal handler (threading.Event), WAV writer (soundfile), recording session lifecycle

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/2 | Not started | - |
| 2. Platform Backends | 0/2 | Not started | - |
| 3. Recording Pipeline | 0/2 | Not started | - |
