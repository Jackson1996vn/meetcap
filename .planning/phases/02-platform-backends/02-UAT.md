---
status: partial
phase: 02-platform-backends
source: [02-01-SUMMARY.md]
started: 2026-05-10T12:00:00Z
updated: 2026-05-10T12:15:00Z
---

## Current Test

[testing paused — 5 items outstanding]

## Tests

### 1. Import and Backend Factory
expected: Running `from meetcap.audio.backends import get_backend; b = get_backend()` returns a MacOSAudioBackend instance without errors.
result: blocked
blocked_by: other
reason: "User deferred all testing to a later session"

### 2. Start System Audio Capture
expected: Calling `b.start(callback)` with a simple callback (e.g. `lambda buf: print(buf.shape, buf.dtype)`) begins capturing. Within a few seconds, the callback fires and prints numpy array shapes with dtype float32. A TCC permission dialog may appear on first run — approve it.
result: blocked
blocked_by: other
reason: "User deferred all testing to a later session"

### 3. Audio Buffer Format
expected: The numpy arrays delivered to the callback are dtype float32, 1-dimensional (mono), and contain plausible audio values (not all zeros when system audio is playing).
result: blocked
blocked_by: other
reason: "User deferred all testing to a later session"

### 4. Stop Capture Cleanly
expected: Calling `b.stop()` returns promptly (under 5 seconds), no errors or tracebacks. After stopping, no more callbacks fire.
result: blocked
blocked_by: other
reason: "User deferred all testing to a later session"

### 5. TCC Permission Error Message
expected: If Screen Recording permission is NOT granted (denied or never prompted), the backend raises a PermissionError with a clear message mentioning System Settings > Privacy & Security > Screen Recording.
result: blocked
blocked_by: other
reason: "User deferred all testing to a later session"

## Summary

total: 5
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 5

## Gaps

[none yet]
