"""Interruptible audio playback using pyaudio for raw PCM/MP3 streams."""

import asyncio
import struct
import subprocess
import threading

from loguru import logger


class StreamPlayer:
    """
    Low-level interruptible audio player.
    Used by TTSRouter when playing pre-buffered audio.

    Uses ffmpeg (system install) for MP3 decoding instead of pydub,
    which avoids the broken ``audioop`` / ``pyaudioop`` import chain.
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

        wav_bytes = b""
        try:
            if fmt == "mp3":
                # Decode MP3 -> WAV (PCM s16le) via ffmpeg pipe
                proc = subprocess.run(
                    [
                        "ffmpeg",
                        "-i", "pipe:0",
                        "-f", "wav",
                        "-acodec", "pcm_s16le",
                        "pipe:1",
                    ],
                    input=audio_bytes,
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    stderr = proc.stderr.decode(errors="replace")[:300]
                    logger.warning(f"ffmpeg decode failed (rc={proc.returncode}): {stderr}")
                    return
                wav_bytes = proc.stdout
            else:
                raise ValueError(f"Unsupported audio format: {fmt}")

            if len(wav_bytes) < 44:
                logger.warning("ffmpeg produced truncated WAV output")
                return

            # Parse WAV header
            channels = struct.unpack_from("<H", wav_bytes, 22)[0]
            rate = struct.unpack_from("<I", wav_bytes, 24)[0]
            bits_per_sample = struct.unpack_from("<H", wav_bytes, 34)[0]
            sample_width = bits_per_sample // 8
            data = wav_bytes[44:]

            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(sample_width),
                channels=channels,
                rate=rate,
                output=True,
            )

            chunk_size = int(rate * sample_width * channels * 0.1)  # 100 ms
            for i in range(0, len(data), chunk_size):
                if self._stop_event.is_set():
                    logger.debug("StreamPlayer: stopped mid-playback")
                    break
                stream.write(data[i : i + chunk_size])

            stream.stop_stream()
            stream.close()
            p.terminate()

        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg decode timed out")
        except Exception as e:
            logger.warning(f"StreamPlayer playback error: {e}")

    def stop(self) -> None:
        """Signal playback to stop after the current chunk."""
        self._stop_event.set()
        logger.debug("StreamPlayer stop signalled")
