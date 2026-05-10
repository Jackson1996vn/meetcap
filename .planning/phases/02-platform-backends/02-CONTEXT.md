# Phase 2: Platform Backends - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement system audio capture backends for macOS (ScreenCaptureKit via PyObjC) and Windows (WASAPI loopback via PyAudioWPatch), behind a shared `SystemAudioBackend` protocol. This phase captures system audio only — mic capture is Phase 3. Backends deliver audio buffers via callbacks to the caller.

</domain>

<decisions>
## Implementation Decisions

### Backend Protocol Design
- **D-01:** Callback-based data delivery — backend calls a user-provided callback with each audio buffer (matches native APIs)
- **D-02:** Protocol covers system audio only — mic capture is handled separately via sounddevice in Phase 3
- **D-03:** Platform detection at import time selects the correct backend automatically
- **D-04:** ScreenCaptureKit captures at the OS mixer level — works regardless of output device (AirPods, speakers, etc.)

### macOS Capture Approach
- **D-05:** Use PyObjC direct bindings to ScreenCaptureKit — no Swift helper subprocess
- **D-06:** Target macOS 15+ (Sequoia through current, including Tahoe 26.x) — no need to support macOS 13/14
- **D-07:** Must retain SCStream delegate as instance attribute to prevent macOS 15 garbage collection bug (PyObjC issue #647)
- **D-08:** Must spin NSRunLoop on the capture thread for callbacks to fire

### Error Handling & Permissions
- **D-09:** When Screen Recording permission is missing, attempt to trigger the OS permission dialog automatically by invoking ScreenCaptureKit (which triggers the system prompt), then retry
- **D-10:** If system audio capture fails mid-session, log a warning and continue — don't kill the whole recording (mic may still be active in Phase 3)

### Audio Data Format
- **D-11:** Output sample rate: 48000 Hz (canonical rate — avoids resampling from most output devices)
- **D-12:** Output channels: mono (speech doesn't benefit from stereo, halves data size)
- **D-13:** Buffer format: numpy float32 arrays delivered via callback

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Research
- `.planning/research/STACK.md` — PyObjC ScreenCaptureKit and PyAudioWPatch version/usage details
- `.planning/research/PITFALLS.md` — SCStream delegate GC bug, WASAPI loopback limitations, sample rate mismatch
- `.planning/research/ARCHITECTURE.md` — SystemAudioBackend protocol design and component boundaries

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/meetcap/config.py` — load_config() returns recordings_dir path, backends can use this for output location
- `src/meetcap/cli.py` — click entry point where backends will be invoked from

### Established Patterns
- TOML config via platformdirs — new backend config (if needed) follows same pattern
- src/meetcap/ package layout — backends go in src/meetcap/audio/ subpackage

### Integration Points
- Phase 3 (Recording Pipeline) will import the backend protocol and instantiate the platform-specific backend
- cli.py will need to detect platform and select backend

</code_context>

<specifics>
## Specific Ideas

- User is on macOS Tahoe 26.x beta — test against latest ScreenCaptureKit APIs
- AirPods/Bluetooth compatibility confirmed at OS mixer level — no special handling needed for system audio

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-platform-backends*
*Context gathered: 2026-05-10*
