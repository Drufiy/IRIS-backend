"""Groq cloud Whisper backend - fast, accurate, no local GPU needed."""

from __future__ import annotations

import io
import wave

import numpy as np


class GroqWhisperBackend:
    """
    Uses Groq's whisper-large-v3-turbo API for cloud ASR.
    Accepts float32 mono audio at 16kHz, returns ASRResult dict.
    """

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo"):
        from groq import Groq

        self.client = Groq(api_key=api_key)
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

        transcription = self.client.audio.transcriptions.create(
            file=buf,
            model=self.model,
            language="en",
            response_format="text",
        )
        text = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
        return {"transcript": text, "confidence": 1.0, "language": "en"}
