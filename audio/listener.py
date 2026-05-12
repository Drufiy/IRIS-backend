"""Always-on microphone listener primitives."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    class _NumpyFallback:
        ndarray = list

        @staticmethod
        def asarray(value):
            return list(value)

    np = _NumpyFallback()


class AudioInputBackend(Protocol):
    """Backend contract for reading audio frames."""

    def read(self, chunk_size: int):
        """Returns the next chunk of mono audio."""


@dataclass(slots=True)
class AudioConfig:
    """Configuration for the microphone listener."""

    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"
    chunk_size: int = 1600


class SoundDeviceBackend:
    """Thin adapter around sounddevice for live microphone capture."""

    def __init__(self, config: AudioConfig):
        self.config = config
        self._stream = None

    def start(self) -> None:
        """Starts the underlying input stream."""
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype=self.config.dtype,
            blocksize=self.config.chunk_size,
        )
        self._stream.start()

    def read(self, chunk_size: int):
        """Reads one chunk from the live stream."""
        if self._stream is None:
            raise RuntimeError("Audio stream is not started.")
        data, _overflowed = self._stream.read(chunk_size)
        return np.asarray(data).reshape(-1)

    def stop(self) -> None:
        """Stops the live stream if it is open."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class AudioListener:
    """Async interface for microphone capture."""

    def __init__(self, config: AudioConfig | None = None, backend: AudioInputBackend | None = None):
        self.config = config or AudioConfig()
        self.backend = backend or SoundDeviceBackend(self.config)
        self._active = False

    async def start(self) -> None:
        """Starts audio capture."""
        if hasattr(self.backend, "start"):
            await asyncio.to_thread(self.backend.start)
        self._active = True

    async def read_chunk(self):
        """Reads the next audio chunk."""
        if not self._active:
            raise RuntimeError("AudioListener is not started.")
        return await asyncio.to_thread(self.backend.read, self.config.chunk_size)

    async def stop(self) -> None:
        """Stops audio capture."""
        self._active = False
        if hasattr(self.backend, "stop"):
            await asyncio.to_thread(self.backend.stop)


class MicListener:
    """Compatibility wrapper for the synchronous event-loop contract."""

    def __init__(self, config: AudioConfig | None = None, backend: AudioInputBackend | None = None):
        self.config = config or AudioConfig()
        self.backend = backend or SoundDeviceBackend(self.config)
        self._active = False

    def start(self) -> None:
        """Starts microphone capture."""
        if hasattr(self.backend, "start"):
            self.backend.start()
        self._active = True

    def get_chunk(self):
        """Returns the next chunk synchronously for the current event loop."""
        if not self._active:
            return None
        return self.backend.read(self.config.chunk_size)

    def stop(self) -> None:
        """Stops microphone capture."""
        self._active = False
        if hasattr(self.backend, "stop"):
            self.backend.stop()
