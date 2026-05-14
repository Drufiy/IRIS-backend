"""ElevenLabs streaming TTS client."""

import asyncio
import io

import httpx
from loguru import logger


class ElevenLabsTTS:
    """
    Streams audio from ElevenLabs and plays it via pyaudio.
    Call stop() from any coroutine to interrupt mid-playback.
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str, model: str = "eleven_turbo_v2") -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
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
        """Synchronous MP3 decode and pyaudio playback."""
        import pyaudio
        from pydub import AudioSegment

        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            player = pyaudio.PyAudio()
            stream = player.open(
                format=player.get_format_from_width(audio.sample_width),
                channels=audio.channels,
                rate=audio.frame_rate,
                output=True,
            )
            chunk_size = int(audio.frame_rate * audio.sample_width * audio.channels * 0.1)
            data = audio.raw_data
            for index in range(0, len(data), chunk_size):
                if self._stop_flag:
                    break
                stream.write(data[index : index + chunk_size])
            stream.stop_stream()
            stream.close()
            player.terminate()
        except Exception as exc:
            logger.warning(f"Audio playback error: {exc}")

    def stop(self) -> None:
        """Signal the streaming loop to stop after the current chunk."""
        self._stop_flag = True
        logger.debug("TTS stop flag set")
