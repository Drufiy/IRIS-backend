"""Unified memory interface used by the rest of IRIS."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from memory.graph import KnowledgeGraph
from memory.long_term import LongTermMemory
from memory.short_term import ShortTermMemory
from memory.vector_store import VectorStore


class MemoryManager:
    """Coordinates short-term, long-term, vector, and graph memory."""

    def __init__(self, config: dict):
        self.short = ShortTermMemory(limit=config.get("short_term_limit", 20))
        self.long = LongTermMemory(path=config.get("long_term_path", "data/long_term_memory.json"))
        self.vectors = VectorStore(
            persist_path=config.get("chroma_path", ".chroma"),
            embedding_model=config.get("embedding_model", "BAAI/bge-m3"),
        )
        self.graph = KnowledgeGraph()
        self.top_k_retrieval = config.get("top_k_retrieval", 5)

    async def store(self, role: str, content: str, tags: list[str] | None = None) -> None:
        """Stores a turn in all memory layers."""
        entry = {
            "id": str(uuid4()),
            "role": role,
            "content": content,
            "tags": tags or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.short.add(entry)
        await self.long.append(entry)
        await self.vectors.add(content, {"role": role, "tags": entry["tags"]}, entry["id"])

    async def retrieve_context(self, query: str, top_k: int | None = None) -> list[dict]:
        """Retrieves relevant context from the vector store."""
        return await self.vectors.search(query, top_k or self.top_k_retrieval)

    async def inject_into_prompt(self, base_messages: list[dict]) -> list[dict]:
        """Prepends memory context to the prompt using the latest user message as the query."""
        if not base_messages:
            return []
        query = base_messages[-1].get("content", "")
        context = await self.retrieve_context(query)
        if not context:
            return list(base_messages)

        lines = [f"- {item['text']}" for item in context if item.get("text")]
        if not lines:
            return list(base_messages)

        memory_message = {
            "role": "system",
            "content": "Relevant memory context:\n" + "\n".join(lines),
        }
        return [memory_message, *base_messages]
