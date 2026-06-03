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

    async def save_interaction(self, interaction: dict[str, Any]) -> None:
        """Stores a durable interaction record for later reflection."""
        store = await self._read_store()
        store["interactions"].append(interaction)
        await self._write_store(store)

    async def read_interactions(self) -> list[dict[str, Any]]:
        """Reads all stored interaction records."""
        store = await self._read_store()
        return list(store["interactions"])

    async def save_reflection(self, reflection: dict[str, Any]) -> None:
        """Stores a durable reflection derived from an interaction."""
        store = await self._read_store()
        store["reflections"].append(reflection)
        await self._write_store(store)

    async def read_reflections(self) -> list[dict[str, Any]]:
        """Reads all stored reflections."""
        store = await self._read_store()
        return list(store["reflections"])

    async def save_improvement_proposal(self, proposal: dict[str, Any]) -> None:
        """Stores a durable self-improvement proposal for later review or execution."""
        store = await self._read_store()
        store["improvement_proposals"].append(proposal)
        await self._write_store(store)

    async def read_improvement_proposals(self) -> list[dict[str, Any]]:
        """Reads all stored self-improvement proposals."""
        store = await self._read_store()
        return list(store["improvement_proposals"])

    async def update_improvement_proposal(self, proposal_id: str, **updates: Any) -> dict[str, Any] | None:
        """Update a stored self-improvement proposal in place."""
        store = await self._read_store()
        for proposal in store["improvement_proposals"]:
            if proposal.get("id") != proposal_id:
                continue
            proposal.update(updates)
            await self._write_store(store)
            return dict(proposal)
        return None

    async def _read_store(self) -> dict[str, list[dict[str, Any]]]:
        """Loads the structured long-term memory store."""
        if not self.path.exists():
            return {"entries": [], "habits": [], "interactions": [], "reflections": [], "improvement_proposals": []}
        raw = await asyncio.to_thread(self.path.read_text, "utf-8")
        if not raw.strip():
            return {"entries": [], "habits": [], "interactions": [], "reflections": [], "improvement_proposals": []}
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return {"entries": parsed, "habits": [], "interactions": [], "reflections": [], "improvement_proposals": []}
        return {
            "entries": list(parsed.get("entries", [])),
            "habits": list(parsed.get("habits", [])),
            "interactions": list(parsed.get("interactions", [])),
            "reflections": list(parsed.get("reflections", [])),
            "improvement_proposals": list(parsed.get("improvement_proposals", [])),
        }

    async def _write_store(self, store: dict[str, list[dict[str, Any]]]) -> None:
        """Persists the structured long-term memory store."""
        await asyncio.to_thread(self.path.write_text, json.dumps(store, indent=2), "utf-8")
