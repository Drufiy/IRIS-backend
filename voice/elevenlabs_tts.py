"""ElevenLabs streaming TTS client."""

import asyncio
import io
import httpx
from loguru import logger


class ElevenLabsTTS:
    """
    Streams audio from ElevenLabs and plays it chunk-by-chunk via pyaudio.
    Call stop() from any coroutine to interrupt mid-playback.
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str, model: str = "eleven_turbo_v2") -> None:
        self.api_key  = api_key
        self.voice_id = voice_id
        self.model    = model
        self.headers  = {"xi-api-key": api_key, "Content-Type": "application/json"}
        self._stop_flag = False

    async def speak(self, text: str) -> None:
        """Stream audio from ElevenLabs and play it. Interruptible via stop()."""
        self._stop_flag = False
        url = f"{self.BASE_URL}/text-to-speech/{self.voice_id}/stream"
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        logger.debug(f"ElevenLabs TTS: speaking {len(text)} chars")

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", url, json=payload, headers=self.headers, timeout=30
                ) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes(chunk_size=4096):
                        if self._stop_flag:
                            logger.debug("TTS stopped by interrupt flag")
                            break
                        await self._play_chunk(chunk)
        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            raise

    async def _play_chunk(self, chunk: bytes) -> None:
        """Decode MP3 bytes and play via pyaudio. Runs in executor to avoid blocking."""
        if not chunk:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._play_sync, chunk)

    def _play_sync(self, chunk: bytes) -> None:
        """Synchronous MP3 decode + pyaudio playback."""
        import pyaudio
        from pydub import AudioSegment

        try:
            audio = AudioSegment.from_file(io.BytesIO(chunk), format="mp3")
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(audio.sample_width),
                channels=audio.channels,
                rate=audio.frame_rate,
                output=True,
            )
            stream.write(audio.raw_data)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logger.warning(f"Audio playback error (chunk may be partial): {e}")

    def stop(self) -> None:
        """Signal the streaming loop to stop after the current chunk."""
        self._stop_flag = True
        logger.debug("TTS stop flag set")
