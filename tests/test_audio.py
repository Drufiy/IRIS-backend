"""Tests for Aryan's audio modules."""

from __future__ import annotations

import unittest

from audio.asr import ASREngine
from audio.interrupt_handler import InterruptHandler
from audio.listener import AudioConfig, AudioListener
from audio.wake_word import WakeWordDetector


class FakeAudioBackend:
    def read(self, chunk_size: int):
        return [1.0] * chunk_size


class FakeASRBackend:
    def transcribe(self, audio) -> dict[str, object]:
        return {
            "transcript": f"heard {len(audio)} samples",
            "confidence": 0.91,
            "language": "en",
        }


class AudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_reads_chunk(self) -> None:
        listener = AudioListener(AudioConfig(chunk_size=8), backend=FakeAudioBackend())
        await listener.start()
        chunk = await listener.read_chunk()
        await listener.stop()
        self.assertEqual(len(chunk), 8)

    async def test_asr_engine_uses_backend(self) -> None:
        engine = ASREngine(backend=FakeASRBackend())
        result = await engine.transcribe([0.0, 0.0, 0.0, 0.0])
        self.assertEqual(result["language"], "en")
        self.assertIn("heard", result["transcript"])

    async def test_wake_word_detector_fires_callback(self) -> None:
        seen: list[str] = []
        detector = WakeWordDetector(["iris"])
        detector.on_wake(seen.append)
        result = await detector.process_text("hey iris open notes")
        self.assertEqual(result, "iris")
        self.assertEqual(seen, ["iris"])

    async def test_interrupt_handler_matches_phrase(self) -> None:
        handler = InterruptHandler(["stop"])
        self.assertTrue(await handler.should_interrupt("please stop now"))
        self.assertFalse(await handler.should_interrupt("carry on"))
