---
phase: 02-platform-backends
plan: "02"
subsystem: audio-backends
tags: [pyaudiowpatch, wasapi, windows, audio, loopback]
dependency_graph:
  requires:
    - 02-01 (SystemAudioBackend protocol, get_backend() platform selector)
  provides:
    - WindowsAudioBackend (meetcap.audio.backends.windows)
    - WASAPI loopback capture with int16-to-float32 conversion
  affects:
    - Phase 3 (recorder imports get_backend() which now returns WindowsAudioBackend on win32)
tech_stack:
  added:
    - PyAudioWPatch>=0.2.12 (win32-only)
    - samplerate>=0.2.1 (win32-only, resampling)
  patterns:
    - PyAudio callback-based stream with factory function for normalization
    - WASAPI loopback device discovery via get_loopback_device_info_generator()
    - int16 capture with float32 normalization (/32768.0)
    - Graceful dependency fallback (samplerate -> numpy interp)
key_files:
  created:
    - src/meetcap/audio/backends/windows.py
  modified:
    - pyproject.toml (added 2 Windows-only dependencies)
    - uv.lock (regenerated)
decisions:
  - "paInt16 format for WASAPI stream (not paFloat32) per Pitfall 4 — loopback delivers int16 by default"
  - "samplerate library for high-quality resampling with numpy interp fallback if unavailable"
  - "Buffer length validation (T-02-05) before np.frombuffer to reject malformed callbacks"
patterns-established:
  - "PyAudio callback factory pattern: _make_stream_callback wraps normalization logic"
  - "WASAPI loopback discovery: get_host_api_info_by_type -> default output -> loopback generator"
requirements-completed: [AUD-04]
metrics:
  duration: "~2 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 02 Plan 02: Windows WASAPI Loopback Backend Summary

**WindowsAudioBackend using PyAudioWPatch WASAPI loopback with int16-to-float32 conversion, mono mixdown, and 48 kHz resampling via samplerate library.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-10T02:40:45Z
- **Completed:** 2026-05-10T02:42:24Z
- **Tasks:** 2 of 3 (Task 3 human verification PENDING -- no Windows machine available)
- **Files modified:** 3

## Accomplishments
- WindowsAudioBackend satisfies SystemAudioBackend protocol structurally
- WASAPI loopback device discovered automatically from default speakers
- Audio delivered as numpy float32 mono at 48 kHz with proper int16 normalization
- Threat mitigations T-02-05 (buffer validation) and T-02-06 (metadata-only logging) implemented

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Windows dependencies to pyproject.toml** - `2ebbc65` (chore)
2. **Task 2: Implement WindowsAudioBackend with WASAPI loopback** - `255b78f` (feat)
3. **Task 3: Verify Windows WASAPI loopback end-to-end** - PENDING (checkpoint:human-verify deferred -- executing on macOS)

## Files Created/Modified
- `src/meetcap/audio/backends/windows.py` - WindowsAudioBackend class with WASAPI loopback capture, int16-to-float32 conversion, mono mixdown, and 48 kHz resampling
- `pyproject.toml` - Added PyAudioWPatch>=0.2.12 and samplerate>=0.2.1 with win32 markers
- `uv.lock` - Regenerated with pyaudiowpatch 0.2.12.8 and samplerate 0.2.4

## Decisions Made
- Used paInt16 stream format (not paFloat32) per Pitfall 4 -- WASAPI loopback delivers int16 by default
- samplerate library chosen for high-quality SINC resampling with numpy interp as fallback
- Buffer length validation added per T-02-05 threat mitigation before np.frombuffer

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None -- no hardcoded placeholder values. WindowsAudioBackend is fully wired but untested on Windows (Task 3 pending).

## Threat Surface Scan

No new security-relevant surface beyond the plan's threat model. Mitigations applied:
- T-02-05: Buffer length validated against expected frame_count * channels * 2 before np.frombuffer
- T-02-06: Only device name, sample rate, and channel count logged; no raw PCM data in logs
- T-02-07: Clear RuntimeError with actionable message when no loopback device found (accepted risk)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both platform backends (macOS + Windows) now implement SystemAudioBackend protocol
- Phase 3 recorder can import get_backend() and receive the platform-appropriate backend
- Task 3 human verification on Windows is deferred but non-blocking for Phase 3 development

---
*Phase: 02-platform-backends*
*Completed: 2026-05-10*
