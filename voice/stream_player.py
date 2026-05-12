"""Interruptible audio playback using pyaudio for raw PCM/MP3 streams."""

import asyncio
import io
import threading
from loguru import logger


class StreamPlayer:
    """
    Low-level interruptible audio player.
    Used by TTSRouter when playing pre-buffered audio.
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._lock = asyncio.Lock()

    async def play_bytes(self, audio_bytes: bytes, fmt: str = "mp3") -> None:
        """Play audio bytes. fmt can be 'mp3' or 'pcm'."""
        self._stop_event.clear()
        loop = asyncio.get_event_loop()
        async with self._lock:
            await loop.run_in_executor(None, self._play_sync, audio_bytes, fmt)

    def _play_sync(self, audio_bytes: bytes, fmt: str) -> None:
        import pyaudio
        from pydub import AudioSegment

        try:
            if fmt == "mp3":
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            else:
                raise ValueError(f"Unsupported audio format: {fmt}")

            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(audio.sample_width),
                channels=audio.channels,
                rate=audio.frame_rate,
                output=True,
            )

            # Write in small chunks so stop_event is checked frequently
            chunk_ms = 100
            chunk_bytes = int(audio.frame_rate * audio.sample_width * audio.channels * chunk_ms / 1000)
            raw = audio.raw_data

            for i in range(0, len(raw), chunk_bytes):
                if self._stop_event.is_set():
                    logger.debug("StreamPlayer: stopped mid-playback")
                    break
                stream.write(raw[i : i + chunk_bytes])

            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            logger.warning(f"StreamPlayer playback error: {e}")

    def stop(self) -> None:
        """Signal playback to stop after the current chunk."""
        self._stop_event.set()
        logger.debug("StreamPlayer stop signalled")
