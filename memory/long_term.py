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
        data = await self.read_all()
        data.append(entry)
        await asyncio.to_thread(self.path.write_text, json.dumps(data, indent=2), "utf-8")

    async def read_all(self) -> list[dict[str, Any]]:
        """Reads all long-term entries."""
        if not self.path.exists():
            return []
        raw = await asyncio.to_thread(self.path.read_text, "utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)
