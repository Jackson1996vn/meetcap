"""Windows WASAPI loopback audio backend via PyAudioWPatch.

Captures system audio using the WASAPI loopback device and delivers
numpy float32 mono arrays at 48 kHz to the user callback.

Requires: PyAudioWPatch >= 0.2.12 (Windows only).
"""

import logging

import numpy as np
import pyaudiowpatch as pyaudio

from meetcap.audio.backends import AudioCallback

logger = logging.getLogger(__name__)


def _find_loopback_device(p: pyaudio.PyAudio) -> dict:
    """Discover the WASAPI loopback device for the default output.

    Uses the PyAudioWPatch loopback device generator to find the
    loopback mirror of the current default WASAPI speakers.

    Args:
        p: An initialised PyAudio instance.

    Returns:
        Device info dict for the loopback device.

    Raises:
        RuntimeError: If WASAPI is unavailable or no loopback device found.
    """
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        raise RuntimeError("WASAPI not available on this system")

    default_speakers = p.get_device_info_by_index(
        wasapi_info["defaultOutputDevice"]
    )

    if default_speakers["isLoopbackDevice"]:
        return default_speakers

    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback

    raise RuntimeError(
        "No WASAPI loopback device found. "
        "Run 'python -m pyaudiowpatch' to list available devices."
    )


def _make_stream_callback(
    user_callback: AudioCallback,
    native_rate: int,
    native_channels: int,
):
    """Build a PyAudio stream callback that normalises audio for the user.

    The returned callback converts raw paInt16 bytes to float32, mixes
    to mono, resamples to 48 kHz if needed, and forwards to *user_callback*.

    Args:
        user_callback: The application callback receiving float32 mono 48 kHz.
        native_rate: Device native sample rate in Hz.
        native_channels: Device native channel count.

    Returns:
        A function compatible with PyAudio's stream_callback signature.
    """
    expected_bytes_per_frame = native_channels * 2  # int16 = 2 bytes

    def _callback(in_data, frame_count, time_info, status):
        # T-02-05: validate buffer length before processing
        expected_length = frame_count * expected_bytes_per_frame
        if len(in_data) != expected_length:
            logger.warning(
                "Buffer size mismatch: got %d bytes, expected %d",
                len(in_data),
                expected_length,
            )
            return (None, pyaudio.paContinue)

        # Convert int16 bytes to float32 normalised to [-1.0, 1.0]
        arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Mix to mono if multi-channel
        if native_channels > 1:
            arr = arr.reshape(-1, native_channels).mean(axis=1)

        # Resample to 48 kHz if device rate differs
        if native_rate != 48000:
            try:
                import samplerate

                arr = samplerate.resample(
                    arr, 48000 / native_rate, "sinc_best"
                )
            except ImportError:
                # Fallback: linear interpolation (lower quality but functional)
                target_len = int(len(arr) * 48000 / native_rate)
                arr = np.interp(
                    np.linspace(0, len(arr) - 1, target_len),
                    np.arange(len(arr)),
                    arr,
                ).astype(np.float32)

        user_callback(arr)
        return (None, pyaudio.paContinue)

    return _callback


class WindowsAudioBackend:
    """System audio capture backend for Windows via WASAPI loopback.

    Satisfies the SystemAudioBackend protocol structurally (no inheritance).
    Uses PyAudioWPatch to open a WASAPI loopback stream on the default
    output device. Audio is delivered as numpy float32 mono at 48 kHz.
    """

    def __init__(self) -> None:
        self._p: pyaudio.PyAudio | None = None
        self._stream = None
        self._running: bool = False

    def start(self, callback: AudioCallback) -> None:
        """Begin WASAPI loopback capture.

        Discovers the default loopback device automatically, opens a
        paInt16 stream, and delivers normalised float32 mono 48 kHz
        buffers to *callback*.

        Args:
            callback: Callable invoked with each audio buffer.

        Raises:
            RuntimeError: If no WASAPI loopback device is found.
        """
        self._p = pyaudio.PyAudio()
        loopback = _find_loopback_device(self._p)

        native_rate = int(loopback["defaultSampleRate"])
        native_channels = max(1, int(loopback.get("maxInputChannels", 2)))

        stream_cb = _make_stream_callback(callback, native_rate, native_channels)

        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=native_rate,
            input=True,
            input_device_index=loopback["index"],
            frames_per_buffer=1024,
            stream_callback=stream_cb,
        )
        self._stream.start_stream()
        self._running = True

        # T-02-06: log only device metadata, never raw PCM data
        logger.info(
            "WASAPI loopback capture started (device: %s, rate: %d, channels: %d)",
            loopback["name"],
            native_rate,
            native_channels,
        )

    def stop(self) -> None:
        """Stop capture and release OS resources."""
        self._running = False
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
        if self._p is not None:
            self._p.terminate()
        self._stream = None
        self._p = None
        logger.info("WASAPI loopback capture stopped")
