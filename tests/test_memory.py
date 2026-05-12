"""Tests for Aryan's memory modules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory.memory_manager import MemoryManager
from memory.short_term import ShortTermMemory


class MemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_term_memory_honors_limit(self) -> None:
        memory = ShortTermMemory(limit=2)
        await memory.add({"content": "one"})
        await memory.add({"content": "two"})
        await memory.add({"content": "three"})
        messages = await memory.get_messages()
        self.assertEqual([item["content"] for item in messages], ["two", "three"])

    async def test_memory_manager_stores_and_retrieves_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            await manager.store("user", "Aryan likes offline models", tags=["preference"])
            await manager.store("user", "Aradhya owns the overlay work", tags=["team"])

            context = await manager.retrieve_context("offline models", top_k=1)
            self.assertEqual(len(context), 1)
            self.assertIn("offline", context[0]["text"])

            prompt = await manager.inject_into_prompt([{"role": "user", "content": "use offline models"}])
            self.assertEqual(prompt[0]["role"], "system")
            self.assertIn("Relevant memory context", prompt[0]["content"])
