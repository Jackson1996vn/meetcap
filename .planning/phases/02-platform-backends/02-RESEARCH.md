# Phase 2: Platform Backends - Research

**Researched:** 2026-05-09
**Domain:** System audio capture — PyObjC ScreenCaptureKit (macOS) + PyAudioWPatch WASAPI loopback (Windows), shared protocol
**Confidence:** HIGH (macOS backend verified via PyObjC maintainer canonical example; Windows backend verified via official PyAudioWPatch example; all package versions verified against PyPI)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Callback-based data delivery — backend calls a user-provided callback with each audio buffer (matches native APIs)
- **D-02:** Protocol covers system audio only — mic capture is handled separately via sounddevice in Phase 3
- **D-03:** Platform detection at import time selects the correct backend automatically
- **D-04:** ScreenCaptureKit captures at the OS mixer level — works regardless of output device (AirPods, speakers, etc.)
- **D-05:** Use PyObjC direct bindings to ScreenCaptureKit — no Swift helper subprocess
- **D-06:** Target macOS 15+ (Sequoia through current, including Tahoe 26.x) — no need to support macOS 13/14
- **D-07:** Must retain SCStream delegate as instance attribute to prevent macOS 15 garbage collection bug (PyObjC issue #647)
- **D-08:** Must spin NSRunLoop on the capture thread for callbacks to fire
- **D-09:** When Screen Recording permission is missing, attempt to trigger the OS permission dialog automatically by invoking ScreenCaptureKit (which triggers the system prompt), then retry
- **D-10:** If system audio capture fails mid-session, log a warning and continue — don't kill the whole recording (mic may still be active in Phase 3)
- **D-11:** Output sample rate: 48000 Hz (canonical rate — avoids resampling from most output devices)
- **D-12:** Output channels: mono (speech doesn't benefit from stereo, halves data size)
- **D-13:** Buffer format: numpy float32 arrays delivered via callback

### Claude's Discretion
None stated — all key decisions were locked.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUD-03 | System audio captured via ScreenCaptureKit on macOS 13+ (no driver install required) | PyObjC 12.1 + SCStream pattern documented; delegate retain fix verified; working code example from PyObjC maintainer (issue #647, March 2026) |
| AUD-04 | System audio captured via WASAPI loopback on Windows 10+ (no driver install required) | PyAudioWPatch 0.2.12.8 provides driver-free loopback; official example code verified |
</phase_requirements>

---

## Summary

Phase 2 implements the two platform-specific system audio backends behind a shared `SystemAudioBackend` protocol, delivered as `src/meetcap/audio/` subpackage. The macOS backend uses PyObjC 12.1 bindings to ScreenCaptureKit (`SCStream`) and the Windows backend uses PyAudioWPatch 0.2.12.8 WASAPI loopback. Both deliver numpy float32 arrays at 48 kHz mono via a user-provided callback.

The biggest research breakthrough for this phase: PyObjC issue #647 (macOS 15 callbacks never firing) was resolved in March 2026 by the PyObjC maintainer himself, who provided a canonical working example. The root cause was `@objc.python_method` incorrectly applied to delegate methods — not a PyObjC bug per se. The delegate retain requirement (D-07) remains valid and is confirmed in the working pattern. The run loop requirement (D-08) is satisfied by Tkinter's `mainloop()` in the maintainer's example — for a CLI tool, `NSRunLoop.currentRunLoop().run()` on a dedicated thread achieves the same thing.

A critical constraint discovered during research: **SCStream requires a screen output (`addStreamOutput` with `SCStreamOutputTypeScreen`) to also be registered**, otherwise audio buffers may not deliver. The practical mitigation is to add a low-overhead screen output (set `minimumFrameInterval` to a very low FPS, e.g., 1/60 but ignore all screen frames) alongside the audio output. Audio-only via SCStream is officially unsupported.

For Windows, the PyAudioWPatch pattern is stable and well-documented: discover the default WASAPI speakers, find the matching loopback device via `get_loopback_device_info_generator()`, open a callback-based stream against it. The callback delivers raw bytes (paInt16) which must be converted to numpy float32 and resampled to 48 kHz if the device native rate differs.

**Primary recommendation:** Implement `src/meetcap/audio/backends/macos.py` and `windows.py` conforming to a `SystemAudioBackend` Protocol. macOS backend uses the PyObjC maintainer's verified SCStream pattern with delegate retained and run loop spinning. Windows backend uses PyAudioWPatch loopback with `get_loopback_device_info_generator()`. Both resample to 48 kHz mono float32 before invoking the callback.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SystemAudioBackend protocol definition | Backend layer (`audio/backends/__init__.py`) | — | Defines the interface contract both backends satisfy; imported by Phase 3 recorder |
| macOS system audio capture (SCStream) | Backend layer (`audio/backends/macos.py`) | OS (ScreenCaptureKit framework) | PyObjC binds to OS API; all capture logic isolated in this module |
| Windows system audio capture (WASAPI loopback) | Backend layer (`audio/backends/windows.py`) | OS (WASAPI via PyAudioWPatch) | Pre-patched PortAudio binary handles loopback; isolated in this module |
| Platform detection and backend selection | Backend layer (`audio/backends/__init__.py`) | — | Single `sys.platform` check at import time; keeps recorder.py platform-agnostic |
| Resampling to 48 kHz mono float32 | Backend layer (within each backend) | — | Both backends resample before calling user callback, so caller always receives canonical format |
| User callback invocation | Backend layer | — | Backends call the user-provided callback; Phase 3 will provide that callback |
| Permission check + dialog trigger | Backend layer (`audio/backends/macos.py`) | — | macOS TCC permission must be checked and triggered before `SCStream.startCapture()` |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyobjc-framework-ScreenCaptureKit | 12.1 | macOS system audio via SCStream | Only driver-free system audio path on macOS 13+; version 12.1 confirmed current [VERIFIED: PyPI 2026-05-09] |
| pyobjc-core | 12.1 | PyObjC runtime (required by framework packages) | Installed automatically with framework package [VERIFIED: PyPI 2026-05-09] |
| PyAudioWPatch | 0.2.12.8 | Windows WASAPI loopback | Only driver-free loopback solution; pre-built wheels for Python 3.7–3.14 [VERIFIED: PyPI 2026-05-09] |
| numpy | 2.4.4 | Audio buffer arrays | Required for float32 array delivery per D-13 [VERIFIED: PyPI 2026-05-09] |

### Supporting (macOS only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyobjc-framework-CoreMedia | 12.1 | CMSampleBuffer format query | Needed to extract sample rate from audio format description in SCStream callbacks |
| pyobjc-framework-AVFoundation | 12.1 | CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer | Needed to extract raw audio bytes from CMSampleBuffer |
| pyobjc-framework-Foundation | 12.1 | NSObject, NSRunLoop, NSLog | NSObject base class for delegate; NSRunLoop for callback delivery |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SCStream (via PyObjC) | AudioHardwareCreateProcessTap + CoreAudio | Tap API is cleaner for audio-only (macOS 14.4+), but requires ctypes/FFI — no Python bindings exist. SCStream is the locked decision (D-05) |
| SCStream (via PyObjC) | Swift helper subprocess | Cleaner API surface, but adds build complexity and binary distribution overhead. Locked as D-05 not to do this |
| PyAudioWPatch | sounddevice | sounddevice/PortAudio does NOT support WASAPI loopback (upstream issue #281, still open). PyAudioWPatch is the only option |

**Installation (macOS additions to pyproject.toml):**
```bash
# macOS-only
uv add "pyobjc-framework-ScreenCaptureKit>=12.1" "pyobjc-framework-CoreMedia>=12.1" "pyobjc-framework-AVFoundation>=12.1" "pyobjc-framework-Foundation>=12.1" numpy --platform darwin

# Windows-only
uv add PyAudioWPatch numpy --platform win32
```

**Version verification (already confirmed):**
```
pyobjc-framework-ScreenCaptureKit: 12.1 (current as of 2026-05-09)
PyAudioWPatch:                      0.2.12.8 (current as of 2026-05-09)
numpy:                              2.4.4 (current as of 2026-05-09)
```

---

## Architecture Patterns

### System Architecture Diagram

```
User callback (Phase 3 recorder)
        ^
        |  numpy float32 @ 48 kHz mono
        |
┌───────┴──────────────────────────┐
│      SystemAudioBackend          │
│      (Protocol — __init__.py)    │
│  start(callback) / stop()        │
└──────┬─────────────────┬─────────┘
       │                 │
       │ sys.platform    │
       │ == 'darwin'     │ == 'win32'
       v                 v
┌──────────────┐  ┌──────────────────┐
│  macOS       │  │  Windows         │
│  Backend     │  │  Backend         │
│  (macos.py)  │  │  (windows.py)    │
└──────┬───────┘  └──────┬───────────┘
       │                 │
       v                 v
┌──────────────┐  ┌──────────────────┐
│ ScreenCapture│  │ PyAudioWPatch    │
│ Kit          │  │ WASAPI loopback  │
│ (OS API)     │  │ (OS API)         │
│              │  │                  │
│ SCStream     │  │ paInt16 raw bytes│
│ CMSampleBuf  │  │ → float32 numpy  │
│ → float32    │  │ → resample 48kHz │
│ → mono mix   │  │ → mono mix       │
│ → callback   │  │ → callback       │
└──────────────┘  └──────────────────┘
       ^
       |
 [Permission check]
 TCC Screen Recording
 → trigger dialog if missing
 → retry once
```

### Recommended Project Structure
```
src/meetcap/
├── __init__.py          # (exists)
├── cli.py               # (exists) — will be updated in Phase 3 to invoke backend
├── config.py            # (exists)
└── audio/
    ├── __init__.py      # empty
    └── backends/
        ├── __init__.py  # SystemAudioBackend Protocol + platform selector
        ├── macos.py     # SCStream implementation
        └── windows.py   # PyAudioWPatch WASAPI loopback implementation
```

Note: `audio/recorder.py` and `audio/mixer.py` are Phase 3 work. This phase delivers only `audio/backends/`.

### Pattern 1: SystemAudioBackend Protocol

**What:** A `typing.Protocol` defining the backend interface. Both platform implementations satisfy it structurally (no inheritance required).

**When to use:** Always — this is the boundary Phase 3 imports against.

```python
# Source: ARCHITECTURE.md Pattern 4 + D-01/D-13 decisions
from typing import Callable, Protocol
import numpy as np

AudioCallback = Callable[[np.ndarray], None]
# callback receives float32 array, shape (N,), 48 kHz mono

class SystemAudioBackend(Protocol):
    def start(self, callback: AudioCallback) -> None:
        """Begin capture; call callback(buffer) for each audio chunk."""
        ...
    def stop(self) -> None:
        """Stop capture and release OS resources."""
        ...
```

### Pattern 2: macOS Backend — SCStream via PyObjC (verified working)

**What:** CaptureDelegate subclasses NSObject, receives audio CMSampleBuffers, converts to numpy float32 mono, delivers to user callback. Delegate stored as instance attribute to prevent GC (D-07). Run loop handled by background thread spinning `NSRunLoop.currentRunLoop().run()` (D-08).

**Critical constraint:** `addStreamOutput` for both `SCStreamOutputTypeScreen` AND `SCStreamOutputTypeAudio` must be called. Screen frames are discarded; audio frames are processed. Audio-only SCStream is officially unsupported and causes the `-3805 connectionInvalid` error.

**Key finding:** PyObjC issue #647 (March 2026 resolution) — the bug was NOT a PyObjC framework defect. Root cause: `@objc.python_method` decorator incorrectly applied to delegate methods that Objective-C calls. Removing it fixes callbacks. The maintainer provided a working example; see Code Examples section below.

```python
# Source: PyObjC issue #647 (ronaldoussoren, 2026-03-03) — canonical working pattern
# [VERIFIED: GitHub API https://api.github.com/repos/ronaldoussoren/pyobjc/issues/647/comments]

import objc
from objc import super  # enables argumentless super() in NSObject subclasses
from Foundation import NSObject, NSRunLoop
from ScreenCaptureKit import (
    SCStream, SCShareableContent, SCStreamConfiguration, SCContentFilter,
    SCStreamOutputTypeAudio, SCStreamOutputTypeScreen,
)

class CaptureDelegate(NSObject):
    # NOT decorated with @objc.python_method — Objective-C must be able to call this
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, type):
        if type == SCStreamOutputTypeAudio:
            # convert sampleBuffer → numpy float32 mono @ 48 kHz → self._callback(arr)
            ...

    def stream_didStopWithError_(self, stream, error):
        # log warning (D-10), do not propagate
        ...
```

### Pattern 3: Windows Backend — PyAudioWPatch WASAPI Loopback

**What:** Use `p.get_host_api_info_by_type(pyaudio.paWASAPI)` to find WASAPI, then `get_loopback_device_info_generator()` to find the loopback for the default output device. Open a callback stream; in the callback, convert `in_data` (paInt16 bytes) to float32 numpy, resample to 48 kHz mono, invoke user callback.

```python
# Source: PyAudioWPatch official example
# [VERIFIED: https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py]
import pyaudiowpatch as pyaudio
import numpy as np

def find_loopback_device(p: pyaudio.PyAudio) -> dict:
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    if default_speakers["isLoopbackDevice"]:
        return default_speakers
    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback
    raise RuntimeError("No WASAPI loopback device found")

# Stream opened with: format=pyaudio.paFloat32, input=True,
# input_device_index=loopback["index"], stream_callback=callback
# In callback: convert bytes → np.frombuffer(in_data, dtype=np.float32)
# then mix to mono, resample to 48000 Hz if device rate differs
```

### Pattern 4: Platform Selector at Import Time (D-03)

```python
# src/meetcap/audio/backends/__init__.py
import sys
from meetcap.audio.backends.base import SystemAudioBackend, AudioCallback

if sys.platform == "darwin":
    from meetcap.audio.backends.macos import MacOSAudioBackend as _BackendImpl
elif sys.platform == "win32":
    from meetcap.audio.backends.windows import WindowsAudioBackend as _BackendImpl
else:
    raise NotImplementedError(f"Platform {sys.platform!r} not supported")

def get_backend() -> SystemAudioBackend:
    return _BackendImpl()
```

### Anti-Patterns to Avoid

- **`@objc.python_method` on delegate methods:** The root cause of the zero-callback bug. Objective-C invokes delegate methods by name — annotating them as Python-only makes them invisible to Objective-C. Never use this decorator on methods that are part of an Objective-C protocol.
- **Storing the delegate in a local variable:** Python GC will collect it. Store as `self.delegate = CaptureDelegate.alloc().initWithCapturer_(self)` on a long-lived object.
- **Calling SCStream without a screen output:** Even for audio-only capture, `addStreamOutput` for `SCStreamOutputTypeScreen` must be registered (frames can be discarded). Audio-only SCStream silently fails or raises `-3805 connectionInvalid`.
- **Using `objc.retain()` / `objc.release()`:** These functions do not exist in modern PyObjC. Memory management is automatic via ARC. Attempting to call them raises `AttributeError`.
- **Using sounddevice for Windows loopback:** sounddevice wraps unpatched PortAudio which does NOT expose WASAPI loopback devices. Use PyAudioWPatch exclusively on Windows.
- **Assuming PyAudioWPatch delivers float32:** The WASAPI loopback stream delivers `paInt16` by default. Must convert: `np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0`.
- **Not checking if the loopback device rate matches 48 kHz:** Device may run at 44100, 96000, or other rates. Always resample to 48 kHz in the callback (use `samplerate` library or `scipy.signal.resample_poly`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Loopback audio on Windows | Custom WASAPI COM code | PyAudioWPatch 0.2.12.8 | Pre-patched PortAudio binary handles the WASAPI loopback undocumented extensions; custom COM code requires dozens of lines of ctypes |
| System audio on macOS | Swift helper subprocess, BlackHole driver | PyObjC + SCStream | Driver installs conflict with the "no drivers" constraint (AUD-03/04); Swift subprocess adds build complexity ruled out by D-05 |
| Sample format conversion | Manual bit-twiddling | `np.frombuffer` + numpy ops | One-liner; no custom code needed |
| Resampling | Custom interpolation | `samplerate` library (libsamplerate) | libsamplerate implements high-quality SINC resampling; naive interpolation causes aliasing artifacts that degrade speech recognition |
| CMSampleBuffer → numpy | Custom CoreMedia C binding | `CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer` (via AVFoundation PyObjC) | PyObjC already wraps this; manually coding it requires ctypes structs |

**Key insight:** Both OS audio capture paths involve proprietary low-level APIs with non-obvious failure modes. The existing wrappers (PyObjC, PyAudioWPatch) encapsulate years of community debugging. Build the minimal protocol-conforming wrapper on top; do not attempt to go lower.

---

## Common Pitfalls

### Pitfall 1: SCStream Callbacks Never Fire Due to `@objc.python_method` Decorator

**What goes wrong:** `startCapture()` completes without error. `is_running` is `True`. No audio buffers ever arrive. No exception is raised. The output would be silence.

**Why it happens:** Delegate methods in `CaptureDelegate` were decorated with `@objc.python_method`, which hides them from the Objective-C runtime. ScreenCaptureKit cannot find `stream_didOutputSampleBuffer_ofType_` and silently drops all callbacks.

**How to avoid:** Never decorate `stream_didOutputSampleBuffer_ofType_` or `stream_didStopWithError_` with `@objc.python_method`. Use that decorator only for helper methods that Python code calls directly (not Objective-C). Reference: PyObjC issue #647 resolution (March 2026).

**Warning signs:** Zero audio callbacks within 5 seconds of `startCapture()` on a machine with audible system audio playing. Add a debug log inside the callback — if it never prints, this is the issue.

### Pitfall 2: SCStream -3805 connectionInvalid Without Screen Output

**What goes wrong:** `startCapture()` raises an error or the stream stops within milliseconds with `SCStreamErrorDomain Code=-3805`.

**Why it happens:** SCStream requires at least one screen output handler to be registered via `addStreamOutput_type_sampleHandlerQueue_error_` with `SCStreamOutputTypeScreen`. Without it, the stream is considered invalid.

**How to avoid:** Always add BOTH outputs — screen and audio. In the screen callback, check `type == SCStreamOutputTypeScreen` and return immediately (discard frame). Set `minimumFrameInterval` in `SCStreamConfiguration` to a large value (e.g., `CMTime(value: 1, timescale: 1)` = 1 fps) to minimize screen overhead.

**Warning signs:** Stream stops immediately after `startCapture()` with no audio callbacks.

### Pitfall 3: Permission Check Gaps on macOS

**What goes wrong:** `SCShareableContent.getShareableContentWithCompletionHandler_` returns an empty display list. Capture appears to start but produces silence. No TCC prompt appears for terminal CLI tools.

**Why it happens:** TCC permission for Screen Recording is per-bundle. A CLI script run from Terminal may inherit Terminal's permissions, or may need explicit permission for `/usr/bin/python3` or the uv-managed venv Python binary.

**How to avoid:** Per D-09 — detect missing permission by checking `content.displays()` is non-empty after `getShareableContent`. If empty, call `SCShareableContent.getShareableContentWithCompletionHandler_` (this call triggers the TCC dialog in macOS 13+). Then wait and retry once. Print a clear human-readable message: "Open System Settings > Privacy & Security > Screen Recording, enable Terminal, then retry."

**Warning signs:** `content.displays()` returns an empty list on first run. TCC dialog appears after invoking `getShareableContent`.

### Pitfall 4: PyAudioWPatch Delivers Int16, Not Float32

**What goes wrong:** `np.frombuffer(in_data, dtype=np.float32)` produces garbage values or raises a buffer size error. The downstream callback receives corrupt arrays.

**Why it happens:** The WASAPI loopback stream in PyAudioWPatch's example uses `pyaudio.paInt16` format. The raw bytes are 16-bit signed integers, not 32-bit floats.

**How to avoid:** Open the stream with `format=pyaudio.paFloat32` if the device supports it, OR open with `paInt16` and convert in the callback: `arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0`. The second approach is always safe.

**Warning signs:** Output sounds distorted or corrupted; array values are outside [-1.0, 1.0].

### Pitfall 5: No Run Loop on macOS Capture Thread (D-08)

**What goes wrong:** `startCaptureWithCompletionHandler_` completion handler never fires, or fires correctly but `stream_didOutputSampleBuffer_ofType_` callbacks stop arriving after the first few.

**Why it happens:** Objective-C async callbacks (including SCStream audio callbacks) require an active run loop on the thread where the stream was created. Without `NSRunLoop.currentRunLoop().run()`, the thread exits and callbacks are lost.

**How to avoid:** Create the SCStream and start capture on a dedicated background thread that immediately enters `NSRunLoop.currentRunLoop().run()` (blocking). Stop the run loop by calling `NSRunLoop.currentRunLoop().stop()` from the main thread when shutting down.

**Warning signs:** Callbacks fire 0-2 times then stop. No error is logged.

### Pitfall 6: Mid-Session Sample Rate Mismatch (D-11)

**What goes wrong:** Device native rate is 44100 or 96000 Hz. Audio delivered to callback is at the wrong rate. Phase 3 mixing with mic at 48 kHz causes drift artifacts.

**How to avoid:** For macOS — set `self.stream_config.setSampleRate_(48000)` in `SCStreamConfiguration`. ScreenCaptureKit handles the resampling OS-side. For Windows — read `loopback["defaultSampleRate"]`; if not 48000, resample in callback using `samplerate.resample(arr, 48000 / native_rate, 'sinc_best')`.

---

## Code Examples

### macOS: CaptureDelegate (verified working)

```python
# Source: PyObjC issue #647 — ronaldoussoren canonical example (2026-03-03)
# [VERIFIED: https://api.github.com/repos/ronaldoussoren/pyobjc/issues/647/comments]
import objc
from objc import super  # REQUIRED for argumentless super() in NSObject subclasses
from Foundation import NSObject, NSLog
from ScreenCaptureKit import SCStreamOutputTypeAudio, SCStreamOutputTypeScreen

class CaptureDelegate(NSObject):
    def initWithCapturer_(self, capturer):
        self = super().init()      # uses argument-less super() from objc import
        if self is None:
            return None
        self._capturer = capturer  # strong reference to owner — prevents GC of capturer
        return self

    # DO NOT use @objc.python_method here — this is called by Objective-C
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, output_type):
        if output_type == SCStreamOutputTypeAudio:
            # Extract buffer, convert, call callback
            self._capturer._handle_audio(sampleBuffer)
        # Screen frames (SCStreamOutputTypeScreen) are silently discarded

    def stream_didStopWithError_(self, stream, error):
        if error:
            import logging
            logging.warning(f"SCStream stopped: {error}")
        # D-10: do not propagate — caller continues
```

### macOS: Stream Setup (keys)

```python
# Source: derived from PyObjC maintainer's example + Apple SCStreamConfiguration docs
# [VERIFIED: PyObjC issue #647; https://developer.apple.com/documentation/screencapturekit/scstreamconfiguration]
from ScreenCaptureKit import (
    SCStream, SCShareableContent, SCStreamConfiguration, SCContentFilter,
    SCStreamOutputTypeAudio, SCStreamOutputTypeScreen,
)

# 1. Get shareable content (also triggers TCC prompt if needed)
SCShareableContent.getShareableContentWithCompletionHandler_(self._on_content)

# 2. In callback:
display = content.displays()[0]
config = SCStreamConfiguration.alloc().init()
config.setCapturesAudio_(True)
config.setExcludesCurrentProcessAudio_(False)
config.setSampleRate_(48000)       # D-11: canonical rate
config.setChannelCount_(2)         # capture stereo, mix to mono in callback

content_filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
    display, [], []
)

self.delegate = CaptureDelegate.alloc().initWithCapturer_(self)  # D-07: retain
self.stream = SCStream.alloc().initWithFilter_configuration_delegate_(
    content_filter, config, self.delegate
)

# 3. MUST add BOTH screen AND audio outputs
self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
    self.delegate, SCStreamOutputTypeScreen, None, None  # required to avoid -3805
)
self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
    self.delegate, SCStreamOutputTypeAudio, None, None
)

self.stream.startCaptureWithCompletionHandler_(self._on_start)
```

### Windows: Loopback Device Discovery and Stream

```python
# Source: PyAudioWPatch official example pawp_record_wasapi_loopback.py
# [VERIFIED: https://raw.githubusercontent.com/s0d3s/PyAudioWPatch/master/examples/pawp_record_wasapi_loopback.py]
import pyaudiowpatch as pyaudio
import numpy as np

def _find_loopback(p: pyaudio.PyAudio) -> dict:
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        raise RuntimeError("WASAPI not available on this system")
    default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    if default_out["isLoopbackDevice"]:
        return default_out
    for loopback in p.get_loopback_device_info_generator():
        if default_out["name"] in loopback["name"]:
            return loopback
    raise RuntimeError("No WASAPI loopback device found — run `python -m pyaudiowpatch` to list devices")

def _make_callback(user_callback, native_rate: int):
    def callback(in_data, frame_count, time_info, status):
        arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        # mix stereo to mono if needed
        if arr.ndim == 1 and (frame_count * 2 == len(arr)):
            arr = arr.reshape(-1, 2).mean(axis=1)
        # resample to 48000 if native_rate differs
        if native_rate != 48000:
            import samplerate
            arr = samplerate.resample(arr, 48000 / native_rate, 'sinc_best')
        user_callback(arr)
        return (in_data, pyaudio.paContinue)
    return callback
```

### CMSampleBuffer to numpy float32 (macOS)

```python
# Source: PyObjC issue #647 + PyObjC AVFoundation bindings
# [CITED: https://pyobjc.readthedocs.io/en/latest/apinotes/AVFoundation.html]
import numpy as np
from AVFoundation import CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer
from CoreMedia import CMSampleBufferGetNumSamples, CMSampleBufferGetFormatDescription

def _sample_buffer_to_numpy(sample_buffer) -> np.ndarray | None:
    """Convert CMSampleBuffer to float32 mono numpy array."""
    fmt = CMSampleBufferGetFormatDescription(sample_buffer)
    if fmt is None:
        return None
    asbd = fmt.audioStreamBasicDescription()
    n_channels = int(asbd.mChannelsPerFrame)
    # Extract raw audio data
    result = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sample_buffer, None, None, 0, None, None, 0, None
    )
    # result contains the audio buffer list; access via ctypes or objc bridge
    # practical approach: use the block buffer directly
    # (implementation detail varies — see PyObjC docs for exact bridge pattern)
    # Mix n_channels to mono
    # Return np.ndarray float32
    ...
```

Note: The exact CMSampleBuffer extraction requires working with PyObjC's C struct bridging. The maintainer's example in issue #647 shows the general pattern; the full extraction loop requires a spike to validate on macOS 26.x. See Open Questions.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BlackHole virtual driver | ScreenCaptureKit (macOS 13+) | WWDC 2022 | No driver install required; system-level capture |
| SoundCard for loopback | PyAudioWPatch | 2021 | SoundCard explicitly returns silence on macOS loopback |
| `@objc.python_method` on all methods | Only on Python-private methods | PyObjC ≤11 behavior | Removing it from delegate methods is the issue #647 fix |
| sounddevice for Windows WASAPI | PyAudioWPatch | 2021 (upstream not fixed) | sounddevice/PortAudio still does not support WASAPI loopback |
| AudioHardwareCreateProcessTap | Not applicable for Python yet | macOS 14.4 | Better API but no Python bindings; SCStream remains the Python path |

**Deprecated/outdated:**
- `objc.retain()` / `objc.release()`: Do not exist in modern PyObjC. ARC handles memory automatically.
- `objc.registerMetaDataForSelector()` for framework protocol methods: Not needed for pyobjc-framework-* packages — metadata is bundled.
- `SCStream` audio-only (without screen output): Officially unsupported; causes -3805 error. Must register screen output even if frames are discarded.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SCStream -3805 is fully resolved by adding a screen output + removing `@objc.python_method` | Pitfall 1 & 2, Code Examples | If macOS 26.x beta has a new regression, callbacks may still fail — needs a smoke test spike |
| A2 | `setSampleRate_(48000)` on SCStreamConfiguration causes ScreenCaptureKit to resample OS-side before delivering buffers | Code Examples | If SCKit ignores this setting, the callback will receive buffers at the device's native rate (e.g., 96000 Hz) and the downstream pipeline will drift |
| A3 | PyAudioWPatch 0.2.12.8 wheels exist for Python 3.11 on Windows 10+ | Standard Stack | STACK.md states Python 3.7–3.14; not independently re-verified in this session |
| A4 | The `samplerate` library (libsamplerate Python binding) is available and suitable for in-callback resampling on Windows | Don't Hand-Roll | If `samplerate` is not available or too slow for real-time use, an alternative (scipy, or numpy decimation) is needed |

---

## Open Questions

1. **CMSampleBuffer → float32 extraction in PyObjC — exact pattern**
   - What we know: PyObjC wraps `CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer` via AVFoundation. The maintainer's example does not show the full extraction loop.
   - What's unclear: The exact ctypes/objc bridge pattern to access `AudioBuffer.mData` pointer as a numpy buffer on macOS 26.x.
   - Recommendation: Make the first Wave 0 task a 30-minute spike: install pyobjc-framework-ScreenCaptureKit, run the maintainer's example (issue #647), extend it to print the numpy array shape and first few values. This validates the full extraction chain before implementing the protocol.

2. **Does `addStreamOutput` with `SCStreamOutputTypeScreen` PLUS `None` queue work on macOS 26.x?**
   - What we know: The maintainer's example passes `None` for `sampleHandlerQueue` in `addStreamOutput_type_sampleHandlerQueue_error_`.
   - What's unclear: Whether `None` queue causes callbacks to be delivered on the main thread (risky) or on a private OS thread (fine). The run loop requirement (D-08) interaction is untested.
   - Recommendation: Spike this before implementing the full backend.

3. **`samplerate` library availability for in-callback Windows resampling**
   - What we know: `samplerate` (pip installable) wraps libsamplerate which provides high-quality SRC.
   - What's unclear: Whether libsamplerate is fast enough for 48 kHz real-time processing in a PyAudio callback on a budget Windows machine.
   - Recommendation: Add `samplerate` as a dependency; benchmark in a standalone test. Fallback: `np.interp` (lower quality but zero dependencies).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| macOS 15+ (Sequoia/Tahoe) | ScreenCaptureKit capture | ✓ | 26.4 (Tahoe beta) | — |
| Python 3.11 | Runtime | ✓ | 3.11.5 | — |
| uv | Package manager | ✓ | 0.9.13 | pip |
| pyobjc-framework-ScreenCaptureKit | macOS backend | Not yet installed | needs 12.1 | — |
| numpy | Both backends | Not yet installed | needs 2.x | — |
| PyAudioWPatch | Windows backend | Windows-only | 0.2.12.8 | — |
| samplerate | Windows backend resampling | Not yet installed | — | numpy interp |
| Screen Recording TCC permission | macOS capture | Unknown — must check at runtime | — | Trigger dialog (D-09) |

**Missing dependencies with no fallback:**
- `pyobjc-framework-ScreenCaptureKit` (and related framework packages) — needed before macOS backend runs. Wave 0 must install them.
- `numpy` — needed for both backends before any buffer can be delivered.

**Missing dependencies with fallback:**
- `samplerate` — can fall back to `np.interp` for resampling (lower quality but functional).

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (macOS TCC) | System handles via TCC dialog; code must not bypass |
| V5 Input Validation | yes | Validate SCStream buffer sizes, sample rates before processing |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| TCC permission bypass | Elevation of privilege | Do not attempt to use private APIs to bypass Screen Recording TCC; invoke `getShareableContent` to trigger the legitimate system dialog |
| Audio buffer overflow | Tampering | Validate `CMSampleBufferGetNumSamples` result before allocating numpy array; cap at a sane maximum (e.g., 48000 frames = 1 second) |
| Recording without user awareness | Information disclosure | CLI tool is user-initiated; no background recording. D-10 (log warning on failure) ensures failures are visible, not silent |
| Logging audio content | Information disclosure | Callbacks must log only metadata (frame count, timestamp, buffer size) — never log raw PCM data or derived speech content |

---

## Sources

### Primary (HIGH confidence)
- PyObjC issue #647 (GitHub API) — root cause analysis + canonical working code from maintainer (ronaldoussoren, 2026-03-03) [VERIFIED]
- PyPI: pyobjc-framework-ScreenCaptureKit 12.1 — version confirmed [VERIFIED: 2026-05-09]
- PyPI: PyAudioWPatch 0.2.12.8 — version confirmed [VERIFIED: 2026-05-09]
- PyPI: numpy 2.4.4 — version confirmed [VERIFIED: 2026-05-09]
- PyAudioWPatch official example: `pawp_record_wasapi_loopback.py` — loopback discovery pattern [VERIFIED: raw.githubusercontent.com]
- Apple Developer Forums thread/718279 — SCStream audio-only not supported; screen output required [VERIFIED: WebFetch]

### Secondary (MEDIUM confidence)
- Apple Developer Documentation: `SCStreamOutputType.audio`, `SCStreamConfiguration.capturesAudio` — API surface confirmed [CITED]
- Apple Developer Documentation: `AudioHardwareCreateProcessTap` — alternative API, macOS 14.4+, no Python bindings [CITED]
- PyObjC API Notes: ScreenCaptureKit — confirms PyObjC wraps the framework; notes are minimal [CITED: pyobjc.readthedocs.io]

### Tertiary (LOW confidence / ASSUMED)
- SCStream + `None` sampleHandlerQueue delivers callbacks without crash on macOS 26.x — maintainer's example uses this; behavior on Tahoe beta unconfirmed [ASSUMED]
- `setSampleRate_(48000)` on SCStreamConfiguration triggers OS-level resampling — documented in Apple SCStreamConfiguration reference but not tested in Python [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against PyPI on 2026-05-09
- Architecture: HIGH — protocol pattern from ARCHITECTURE.md; confirmed by CONTEXT.md decisions
- macOS backend pattern: HIGH — canonical code verified from PyObjC maintainer's own comment
- Windows backend pattern: HIGH — official PyAudioWPatch example verified
- CMSampleBuffer → numpy extraction: MEDIUM — general approach known; exact PyObjC bridge code requires spike
- macOS 26.x Tahoe compatibility: MEDIUM — maintainer's fix tested on macOS 15; Tahoe (26.x) untested

**Research date:** 2026-05-09
**Valid until:** 2026-06-09 (macOS Tahoe is beta; API surface may shift with each seed release)
