"""System audio backend protocol and platform selector.

Exports:
    AudioCallback: Type alias for the audio buffer callback.
    SystemAudioBackend: Protocol defining the backend interface.
    get_backend: Factory returning the platform-appropriate backend instance.
"""
import sys
from typing import Callable, Protocol

import numpy as np

# AudioCallback receives a float32 numpy array, shape (N,), 48 kHz mono (per D-01, D-13)
AudioCallback = Callable[[np.ndarray], None]


class SystemAudioBackend(Protocol):
    """Protocol for system audio capture backends.

    Both platform implementations satisfy this protocol structurally —
    no inheritance from this class is required (structural subtyping).
    """

    def start(self, callback: AudioCallback) -> None:
        """Begin system audio capture.

        Calls callback(buffer) for each audio chunk delivered as a
        numpy float32 array of shape (N,) at 48 kHz mono (per D-11–D-13).

        Args:
            callback: Callable invoked with each audio buffer.
        """
        ...

    def stop(self) -> None:
        """Stop capture and release OS resources."""
        ...


def get_backend() -> "SystemAudioBackend":
    """Return the platform-appropriate system audio backend instance.

    Platform detection uses sys.platform (per D-03).

    Returns:
        A backend instance conforming to SystemAudioBackend.

    Raises:
        NotImplementedError: If the current platform is not supported.
    """
    if sys.platform == "darwin":
        from meetcap.audio.backends.macos import MacOSAudioBackend
        return MacOSAudioBackend()
    elif sys.platform == "win32":
        from meetcap.audio.backends.windows import WindowsAudioBackend
        return WindowsAudioBackend()
    else:
        raise NotImplementedError(f"Platform {sys.platform!r} not supported")
