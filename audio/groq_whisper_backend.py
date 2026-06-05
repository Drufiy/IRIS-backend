"""Groq cloud Whisper backend - fast, accurate, no local GPU needed."""

from __future__ import annotations

import io
import wave

import numpy as np
from loguru import logger


class GroqWhisperBackend:
    """
    Uses Groq's whisper-large-v3-turbo API for cloud ASR.
    Accepts float32 mono audio at 16kHz, returns ASRResult dict.
    """

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo", base_url: str | None = None):
        from groq import Groq

        resolved_url = base_url or self.DEFAULT_BASE_URL
        self.client = Groq(api_key=api_key, base_url=resolved_url)
        self.model = model

    def transcribe(self, audio) -> dict:
        audio_np = np.asarray(audio, dtype=np.float32)
        if audio_np.size == 0:
            return {"transcript": "", "confidence": 1.0, "language": "en"}

        pcm = (audio_np * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())
        buf.seek(0)
        buf.name = "audio.wav"

        try:
            transcription = self.client.audio.transcriptions.create(
                file=buf,
                model=self.model,
                language="en",
                response_format="verbose_json",
            )
        except Exception as exc:  # pragma: no cover - network/provider failures
            logger.error(f"Groq ASR error: {exc}")
            return {"transcript": "", "confidence": 0.0, "language": "en"}

        text = self._extract_text(transcription)
        if not text:
            logger.warning(
                f"Groq ASR returned an empty transcript (type={type(transcription).__name__})"
            )
        return {"transcript": text, "confidence": 1.0 if text else 0.0, "language": "en"}

    @staticmethod
    def _extract_text(transcription) -> str:
        """Coerce Groq SDK responses into a plain transcript string."""
        if transcription is None:
            return ""
        if isinstance(transcription, str):
            return transcription.strip()
        if isinstance(transcription, (int, float, bool)):
            return str(transcription).strip()
        if isinstance(transcription, dict):
            for key in ("text", "transcript", "content", "message"):
                value = transcription.get(key)
                if value is None:
                    continue
                if isinstance(value, str):
                    return value.strip()
                return str(value).strip()
            return str(transcription).strip()

        for attr in ("text", "transcript", "content"):
            value = getattr(transcription, attr, None)
            if value is None:
                continue
            if isinstance(value, str):
                return value.strip()
            return str(value).strip()

        if hasattr(transcription, "model_dump"):
            try:
                data = transcription.model_dump()
                return GroqWhisperBackend._extract_text(data)
            except Exception:
                pass

        return str(transcription).strip()
