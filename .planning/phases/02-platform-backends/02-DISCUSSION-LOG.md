# Phase 2: Platform Backends - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 02-platform-backends
**Areas discussed:** Backend protocol design, macOS capture approach, Error handling & permissions, Audio data format

---

## Backend Protocol Design

| Option | Description | Selected |
|--------|-------------|----------|
| Callback-based (Recommended) | Backend calls user-provided callback with each audio buffer | ✓ |
| Queue-based | Backend pushes to thread-safe queue, caller pulls | |
| You decide | Claude picks | |

**User's choice:** Callback-based

| Option | Description | Selected |
|--------|-------------|----------|
| System audio only (Recommended) | Phase 2 backends capture system audio only | ✓ |
| Both mic + system | Single backend handles both | |

**User's choice:** System audio only (confirmed AirPods/Bluetooth works at OS mixer level)

---

## macOS Capture Approach

| Option | Description | Selected |
|--------|-------------|----------|
| PyObjC direct (Recommended) | Python bindings, careful delegate retention | ✓ |
| Swift helper binary | Compiled Swift subprocess | |
| You decide | Claude picks | |

**User's choice:** PyObjC direct

| Option | Description | Selected |
|--------|-------------|----------|
| macOS 13+ only | ScreenCaptureKit minimum | |
| macOS 14+ only | Newer, more stable APIs | |

**User's choice:** macOS 15+ through current (Tahoe 26.x) — user is on Tahoe beta, target LTS to current

---

## Error Handling & Permissions

| Option | Description | Selected |
|--------|-------------|----------|
| Print error with System Settings path | Manual permission grant | |
| Trigger OS permission dialog automatically | Invoke ScreenCaptureKit to trigger prompt, then retry | ✓ |
| You decide | Claude picks | |

**User's choice:** Trigger OS permission dialog automatically

| Option | Description | Selected |
|--------|-------------|----------|
| Log warning and continue (Recommended) | Keep other recording alive | ✓ |
| Stop everything | Fatal error | |
| You decide | Claude picks | |

**User's choice:** Log warning and continue

---

## Audio Data Format

| Option | Description | Selected |
|--------|-------------|----------|
| 48000 Hz (Recommended) | Standard system audio rate | ✓ |
| 16000 Hz | Whisper native, needs downsampling | |
| You decide | Claude picks | |

**User's choice:** 48000 Hz

| Option | Description | Selected |
|--------|-------------|----------|
| Mono (Recommended) | Speech, halves data | ✓ |
| Stereo | Preserve original mix | |

**User's choice:** Mono

---

## Claude's Discretion

- Backend file/module organization within src/meetcap/audio/
- Numpy buffer size for callbacks

## Deferred Ideas

None
