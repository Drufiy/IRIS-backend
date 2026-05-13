"""Persistent long-term memory storage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class LongTermMemory:
    """Stores durable user facts and events on disk."""

    def __init__(self, path: str = "data/long_term_memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def append(self, entry: dict[str, Any]) -> None:
        """Appends an entry to the on-disk memory log."""
        store = await self._read_store()
        store["entries"].append(entry)
        await self._write_store(store)

    async def read_all(self) -> list[dict[str, Any]]:
        """Reads all long-term entries."""
        store = await self._read_store()
        return list(store["entries"])

    async def save_habit(self, habit: dict[str, Any]) -> None:
        """Stores a durable habit or preference pattern."""
        store = await self._read_store()
        store["habits"].append(habit)
        await self._write_store(store)

    async def read_habits(self) -> list[dict[str, Any]]:
        """Reads all learned habits."""
        store = await self._read_store()
        return list(store["habits"])

    async def _read_store(self) -> dict[str, list[dict[str, Any]]]:
        """Loads the structured long-term memory store."""
        if not self.path.exists():
            return {"entries": [], "habits": []}
        raw = await asyncio.to_thread(self.path.read_text, "utf-8")
        if not raw.strip():
            return {"entries": [], "habits": []}
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return {"entries": parsed, "habits": []}
        return {
            "entries": list(parsed.get("entries", [])),
            "habits": list(parsed.get("habits", [])),
        }

    async def _write_store(self, store: dict[str, list[dict[str, Any]]]) -> None:
        """Persists the structured long-term memory store."""
        await asyncio.to_thread(self.path.write_text, json.dumps(store, indent=2), "utf-8")
