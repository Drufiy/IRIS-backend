"""ElevenLabs streaming TTS client."""

import asyncio
import struct
import subprocess

import httpx
from loguru import logger


class ElevenLabsTTS:
    """
    Streams audio from ElevenLabs and plays it via pyaudio.
    Call stop() from any coroutine to interrupt mid-playback.

    Uses ffmpeg (system install) for MP3 decoding instead of pydub,
    which avoids the broken ``audioop`` / ``pyaudioop`` import chain
    that plagues newer Python installations.
    """

    DEFAULT_BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str, model: str = "eleven_turbo_v2_5", base_url: str | None = None) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        self._stop_flag = False

    async def speak(self, text: str) -> None:
        """Stream audio from ElevenLabs and play it. Interruptible via stop()."""
        self._stop_flag = False
        url = f"{self.base_url}/text-to-speech/{self.voice_id}/stream"
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        logger.debug(f"ElevenLabs TTS: speaking {len(text)} chars")

        chunks: list[bytes] = []
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", url, json=payload, headers=self.headers, timeout=30
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if self._stop_flag:
                            break
                        if chunk:
                            chunks.append(chunk)
        except httpx.HTTPStatusError as exc:
            logger.error(f"ElevenLabs API error {exc.response.status_code}")
            raise
        except Exception as exc:
            logger.error(f"ElevenLabs TTS error: {exc}")
            raise

        if chunks and not self._stop_flag:
            audio_bytes = b"".join(chunks)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._play_sync, audio_bytes)

    def _play_sync(self, audio_bytes: bytes) -> None:
        """Decode MP3 bytes via ffmpeg and play with pyaudio."""
        import pyaudio

        try:
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
            if len(wav_bytes) < 44:
                logger.warning("ffmpeg produced truncated WAV output")
                return

            # Parse WAV header
            channels = struct.unpack_from("<H", wav_bytes, 22)[0]
            rate = struct.unpack_from("<I", wav_bytes, 24)[0]
            bits_per_sample = struct.unpack_from("<H", wav_bytes, 34)[0]
            sample_width = bits_per_sample // 8

            # Audio data starts after the 44-byte PCM WAV header
            data = wav_bytes[44:]

            player = pyaudio.PyAudio()
            stream = player.open(
                format=player.get_format_from_width(sample_width),
                channels=channels,
                rate=rate,
                output=True,
            )
            chunk_size = int(rate * sample_width * channels * 0.1)  # 100 ms
            for i in range(0, len(data), chunk_size):
                if self._stop_flag:
                    break
                stream.write(data[i : i + chunk_size])
            stream.stop_stream()
            stream.close()
            player.terminate()
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg decode timed out")
        except Exception as exc:
            logger.warning(f"Audio playback error: {exc}")

    def stop(self) -> None:
        """Signal the streaming loop to stop after the current chunk."""
        self._stop_flag = True
        logger.debug("TTS stop flag set")
