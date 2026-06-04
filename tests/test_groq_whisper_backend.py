"""Regression tests for Groq Whisper response parsing."""

from __future__ import annotations

import unittest

from audio.groq_whisper_backend import GroqWhisperBackend


class _ModelLike:
    def __init__(self, text):
        self.text = text


class GroqWhisperBackendTests(unittest.TestCase):
    def test_extract_text_handles_plain_string(self) -> None:
        self.assertEqual(GroqWhisperBackend._extract_text("  hello world  "), "hello world")

    def test_extract_text_handles_model_like_object(self) -> None:
        self.assertEqual(
            GroqWhisperBackend._extract_text(_ModelLike("  hello from model  ")),
            "hello from model",
        )

    def test_extract_text_handles_dict_payload(self) -> None:
        self.assertEqual(
            GroqWhisperBackend._extract_text({"text": "  hello from dict  "}),
            "hello from dict",
        )

    def test_extract_text_handles_numeric_payload(self) -> None:
        self.assertEqual(GroqWhisperBackend._extract_text(123), "123")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
