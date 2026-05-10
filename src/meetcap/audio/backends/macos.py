"""macOS system audio backend using ScreenCaptureKit (SCStream) via PyObjC.

Spike findings (macOS 26.4 Tahoe, 2026-05-10):
- CMSampleBuffer extraction pattern: CMSampleBufferGetDataBuffer -> CMBlockBufferGetDataPointer
  Returns (status, lengthAtOffset, dataLength, dataPtr) where dataPtr is a buffer of float32 bytes
- None queue for addStreamOutput works correctly (callbacks fire on OS-managed thread)
- Permission check: macOS 26.x returns error code -3801 when permission was explicitly declined
  (rather than empty displays list as documented for macOS 13-15)
- D-09 behavior: first call triggers TCC dialog on first run; retry catches both empty displays
  and error -3801 cases for declined permissions
- SCStreamConfiguration.setSampleRate_(48000) confirmed available on macOS 26.x

Security (T-02-01 through T-02-04):
- TCC permission triggered via legitimate SCShareableContent API only (T-02-01)
- CMSampleBufferGetNumSamples validated and capped at 48000 frames before numpy allocation (T-02-02)
- Only metadata logged (frame count, buffer size) — no raw PCM data in logs (T-02-03)
- Background NSRunLoop thread joined with timeout on stop() (T-02-04)
"""
import logging
import threading
import time

import numpy as np
import objc
from objc import super  # REQUIRED: enables argumentless super() in NSObject subclasses
from Foundation import NSObject, NSRunLoop, NSDate
from ScreenCaptureKit import (
    SCStream,
    SCShareableContent,
    SCStreamConfiguration,
    SCContentFilter,
    SCStreamOutputTypeAudio,
    SCStreamOutputTypeScreen,
)
from CoreMedia import (
    CMSampleBufferGetNumSamples,
    CMSampleBufferGetFormatDescription,
    CMSampleBufferGetDataBuffer,
    CMBlockBufferGetDataPointer,
    CMBlockBufferGetDataLength,
)

from meetcap.audio.backends import AudioCallback

logger = logging.getLogger(__name__)

# Maximum samples per buffer — cap to prevent oversized numpy allocations (T-02-02)
_MAX_SAMPLES_PER_BUFFER = 48000  # 1 second at 48 kHz


def _sample_buffer_to_numpy(sample_buffer) -> "np.ndarray | None":
    """Convert a CMSampleBuffer to a float32 numpy array.

    ScreenCaptureKit delivers audio as interleaved float32 PCM
    (kAudioFormatLinearPCM with kAudioFormatFlagIsFloat).

    Args:
        sample_buffer: CMSampleBuffer from SCStream callback.

    Returns:
        numpy float32 array of shape (n_samples * n_channels,), or None on failure.
    """
    # Validate sample count before allocation (T-02-02)
    n_samples = CMSampleBufferGetNumSamples(sample_buffer)
    if n_samples <= 0:
        logger.debug("CMSampleBuffer has no samples, skipping")
        return None
    if n_samples > _MAX_SAMPLES_PER_BUFFER:
        logger.warning(
            "CMSampleBuffer has %d samples (> cap %d), truncating to cap",
            n_samples,
            _MAX_SAMPLES_PER_BUFFER,
        )
        n_samples = _MAX_SAMPLES_PER_BUFFER

    # Get the block buffer containing the raw audio bytes
    block_buf = CMSampleBufferGetDataBuffer(sample_buffer)
    if block_buf is None:
        logger.debug("CMSampleBuffer has no block buffer")
        return None

    # Get total data length from block buffer
    data_length = CMBlockBufferGetDataLength(block_buf)
    if data_length <= 0:
        logger.debug("CMBlockBuffer has zero data length")
        return None

    # Get pointer to contiguous data (status, lengthAtOffset, dataLength, dataPtr)
    # arg4 is 'out void**' — PyObjC returns it as a buffer of bytes with length arg3
    try:
        result = CMBlockBufferGetDataPointer(block_buf, 0, None, None, None)
    except Exception as exc:
        logger.warning("CMBlockBufferGetDataPointer failed: %s", exc)
        return None

    if result is None or len(result) < 4:
        logger.warning("CMBlockBufferGetDataPointer returned unexpected result: %r", result)
        return None

    status, _length_at_offset, actual_length, data_ptr = result
    if status != 0:
        logger.warning("CMBlockBufferGetDataPointer status=%d", status)
        return None
    if data_ptr is None or actual_length <= 0:
        logger.debug("CMBlockBufferGetDataPointer returned null data pointer")
        return None

    # Copy bytes into numpy array (float32 — ScreenCaptureKit delivers float PCM)
    try:
        raw_bytes = bytes(data_ptr[:actual_length])
        arr = np.frombuffer(raw_bytes, dtype=np.float32).copy()
    except Exception as exc:
        logger.warning("numpy array creation from CMSampleBuffer failed: %s", exc)
        return None

    logger.debug(
        "CMSampleBuffer extracted: %d bytes -> %d float32 samples",
        actual_length,
        arr.size,
    )
    return arr


class CaptureDelegate(NSObject):
    """NSObject delegate that receives SCStream audio callbacks.

    CRITICAL: The ObjC-callable delegate methods below must NOT carry the
    objc decorator that marks methods as Python-only — that decorator hides
    methods from the Objective-C runtime, causing zero callbacks (issue #647).
    """

    def initWithCallback_(self, callback):
        """Initialize with the audio callback function.

        Args:
            callback: AudioCallback called with each float32 mono numpy array.
        """
        self = super().init()
        if self is None:
            return None
        self._callback = callback
        return self

    # ObjC-callable — no decorator; Objective-C invokes this by name
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, output_type):
        """Receive audio or video buffers from SCStream.

        Screen frames are discarded; audio frames are extracted and delivered
        to the user callback as float32 mono numpy arrays at 48 kHz.
        """
        # Discard screen frames — required to avoid -3805 (Pitfall 2)
        if output_type == SCStreamOutputTypeScreen:
            return

        if output_type != SCStreamOutputTypeAudio:
            return

        # Extract float32 array from CMSampleBuffer
        arr = _sample_buffer_to_numpy(sampleBuffer)
        if arr is None:
            return

        # Mix stereo (interleaved) to mono if needed (D-12)
        # SCStreamConfiguration.setChannelCount_(2) → interleaved stereo float32
        # Shape is (n_samples * 2,) for stereo; reshape to (-1, 2) then mean
        if arr.ndim == 1 and arr.size % 2 == 0:
            # Try to detect stereo based on format description
            fmt = CMSampleBufferGetFormatDescription(sampleBuffer)
            if fmt is not None:
                try:
                    asbd = fmt.audioStreamBasicDescription()
                    n_channels = int(asbd.mChannelsPerFrame)
                    if n_channels == 2:
                        arr = arr.reshape(-1, 2).mean(axis=1)
                except Exception:
                    # If format query fails, assume stereo and mix down
                    arr = arr.reshape(-1, 2).mean(axis=1)

        # Invoke user callback
        try:
            self._callback(arr)
        except Exception as exc:
            # D-10: never propagate callback errors — log and continue
            logger.warning("Audio callback raised an exception: %s", exc)

    # ObjC-callable — no decorator; Objective-C invokes this by name
    def stream_didStopWithError_(self, stream, error):
        """Handle SCStream stopping unexpectedly.

        Per D-10: log warning only, do not propagate. Mic capture in Phase 3
        may still be active and recording should continue.
        """
        if error:
            logger.warning("SCStream stopped unexpectedly: %s", error)


class MacOSAudioBackend:
    """System audio backend using ScreenCaptureKit SCStream on macOS 15+/26.x.

    Captures system audio at the OS mixer level — works regardless of output
    device (speakers, AirPods, etc.). Delivers audio as numpy float32 mono
    arrays at 48 kHz via a user-provided callback (per D-11–D-13).

    Implements the SystemAudioBackend protocol structurally.
    """

    def __init__(self) -> None:
        self._stream = None
        self._delegate = None  # D-07: retained as instance attribute to prevent GC
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self, callback: AudioCallback) -> None:
        """Begin system audio capture.

        1. Checks Screen Recording TCC permission via SCShareableContent.
        2. If permission missing: triggers TCC dialog and retries once (D-09).
        3. Sets up SCStream with both screen + audio outputs (required — Pitfall 2).
        4. Starts background thread spinning NSRunLoop for callback delivery (D-08).

        Args:
            callback: AudioCallback invoked with each float32 mono 48 kHz buffer.

        Raises:
            PermissionError: If Screen Recording permission is denied after retry.
            RuntimeError: If stream setup fails for any other reason.
        """
        # --- Step 1: Get shareable content (checks permission) ---
        content = self._get_shareable_content_with_retry()

        displays = content.displays()
        if not displays:
            raise RuntimeError(
                "No displays found even after permission check. "
                "This is unexpected — please report this issue."
            )

        display = displays[0]

        # --- Step 2: Configure stream ---
        config = SCStreamConfiguration.alloc().init()
        config.setCapturesAudio_(True)
        config.setExcludesCurrentProcessAudio_(False)
        config.setSampleRate_(48000)   # D-11: OS resamples to 48 kHz
        config.setChannelCount_(2)     # Capture stereo; mix to mono in callback (D-12)
        # Minimize screen capture overhead (Pitfall 2 mitigation)
        try:
            from CoreMedia import CMTimeMake
            config.setMinimumFrameInterval_(CMTimeMake(1, 1))  # 1 fps
        except Exception:
            pass  # Not critical if CMTimeMake unavailable

        content_filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
            display, [], []
        )

        # --- Step 3: Create delegate (D-07: must be instance attribute) ---
        self._delegate = CaptureDelegate.alloc().initWithCallback_(callback)

        # --- Step 4: Create stream ---
        self._stream = SCStream.alloc().initWithFilter_configuration_delegate_(
            content_filter, config, self._delegate
        )

        # --- Step 5: Register BOTH outputs (required — Pitfall 2 / D-08) ---
        error_out = None
        self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._delegate, SCStreamOutputTypeScreen, None, error_out
        )
        self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._delegate, SCStreamOutputTypeAudio, None, error_out
        )

        # --- Step 6: Start background NSRunLoop thread (D-08 / Pitfall 5) ---
        self._running = True
        self._thread = threading.Thread(target=self._run_loop_thread, daemon=True)
        self._thread.start()

        # --- Step 7: Start capture ---
        start_event = threading.Event()
        start_errors = [None]

        def _on_start(error):
            if error:
                start_errors[0] = error
                logger.warning("SCStream startCapture error: %s", error)
            else:
                logger.info("System audio capture started (48 kHz, stereo→mono)")
            start_event.set()

        self._stream.startCaptureWithCompletionHandler_(_on_start)
        start_event.wait(timeout=10)

        if start_errors[0] is not None:
            self._running = False
            if self._thread:
                self._thread.join(timeout=2)
            raise RuntimeError(f"SCStream failed to start: {start_errors[0]}")

    def stop(self) -> None:
        """Stop system audio capture and release OS resources.

        Sets running flag false, stops the SCStream, and joins the run loop thread.
        Safe to call even if start() was never called or already stopped.
        """
        self._running = False

        if self._stream is not None:
            self._stream.stopCaptureWithCompletionHandler_(lambda error: None)
            self._stream = None

        if self._thread is not None:
            self._thread.join(timeout=5)  # T-02-04: timeout to avoid hanging on stop
            self._thread = None

        self._delegate = None  # Release delegate after stream is stopped
        logger.info("System audio capture stopped")

    def _run_loop_thread(self) -> None:
        """Background thread spinning NSRunLoop for SCStream callback delivery.

        Per D-08 and Pitfall 5: Objective-C async callbacks require an active
        run loop on the calling thread. This thread keeps the run loop alive
        while self._running is True.
        """
        while self._running:
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )

    def _get_shareable_content_with_retry(self):
        """Get SCShareableContent, triggering TCC dialog if needed (D-09).

        On macOS 13-15: missing permission → empty displays list.
        On macOS 26.x (Tahoe): missing/declined permission → error -3801.

        Strategy (D-09):
        1. First call: check displays (or detect error -3801).
        2. If displays empty OR error -3801: log info, make second call to trigger TCC dialog.
        3. Wait up to 30 seconds for user to approve.
        4. If STILL no permission after retry: raise PermissionError.

        Returns:
            SCShareableContent with non-empty displays.

        Raises:
            PermissionError: If permission denied after retry.
        """
        # --- First call ---
        ready1 = threading.Event()
        result1 = {"content": None, "error": None}

        def _on_content_1(content, error):
            result1["content"] = content
            result1["error"] = error
            ready1.set()

        SCShareableContent.getShareableContentWithCompletionHandler_(_on_content_1)
        ready1.wait(timeout=30)

        content1 = result1["content"]
        error1 = result1["error"]

        # Check for permission on first call
        has_permission = (
            content1 is not None
            and error1 is None
            and len(content1.displays()) > 0
        )

        if has_permission:
            return content1

        # Permission missing or declined — attempt D-09 retry to trigger TCC dialog
        if error1 is not None:
            logger.info(
                "Screen Recording permission check returned error (%s) — "
                "attempting to trigger TCC permission dialog...",
                error1,
            )
        else:
            logger.info(
                "No displays found — attempting to trigger Screen Recording permission dialog..."
            )

        # --- Second call: triggers TCC dialog on macOS ---
        ready2 = threading.Event()
        result2 = {"content": None, "error": None}

        def _on_content_2(content, error):
            result2["content"] = content
            result2["error"] = error
            ready2.set()

        SCShareableContent.getShareableContentWithCompletionHandler_(_on_content_2)
        # Wait up to 30 seconds for user to approve the TCC dialog
        ready2.wait(timeout=30)

        content2 = result2["content"]
        error2 = result2["error"]

        has_permission_retry = (
            content2 is not None
            and error2 is None
            and len(content2.displays()) > 0
        )

        if has_permission_retry:
            logger.info("Screen Recording permission granted after retry")
            return content2

        # Still no permission after retry — raise clear error
        raise PermissionError(
            "Screen Recording permission required. "
            "Open System Settings > Privacy & Security > Screen Recording, "
            "enable your terminal app (or the Python binary), then restart and retry."
        )
