"""FasterWhisper ASR backend — drop-in for ASREngine."""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel


class FasterWhisperBackend:
    """
    Wraps faster-whisper as an ASRBackend.

    Uses the 'tiny' model by default for low latency on CPU.
    Swap to 'base' or 'small' for better accuracy if hardware allows.
    """

    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio) -> dict:
        """
        Transcribes a numpy float32 audio array at 16 kHz mono.
        Returns ASRResult-compatible dict.
        """
        audio_np = np.asarray(audio, dtype=np.float32)
        if audio_np.size == 0:
            return {"transcript": "", "confidence": 0.0, "language": "en"}

        segments, info = self.model.transcribe(
            audio_np,
            beam_size=1,
            language="en",
            vad_filter=True,          # skip silent segments
            vad_parameters={"min_silence_duration_ms": 300},
        )
        transcript = " ".join(seg.text for seg in segments).strip()
        return {
            "transcript": transcript,
            "confidence": 1.0,
            "language": info.language,
        }
