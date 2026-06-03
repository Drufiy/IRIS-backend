"""Unified memory interface used by the rest of IRIS."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from uuid import uuid4

from memory.graph import KnowledgeGraph
from memory.long_term import LongTermMemory
from memory.self_improvement import SelfImprovementManager
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
        self.habit_limit = config.get("habit_retrieval_limit", 3)
        self.self_improvement = SelfImprovementManager(
            self.long,
            retrieval_limit=config.get("interaction_retrieval_limit", 10),
        )

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
        await self._index_graph(entry)

    async def retrieve_context(self, query: str, top_k: int | None = None) -> list[dict]:
        """Retrieves relevant context from the vector store."""
        limit = top_k or self.top_k_retrieval
        vector_results = await self.vectors.search(query, limit)
        habit_results = await self._matching_habits(query)
        graph_results = await self._graph_context(query)

        merged: list[dict] = []
        seen_keys: set[str] = set()
        for item in [*vector_results, *habit_results, *graph_results]:
            text = item.get("text", "")
            key = f"{item.get('metadata', {}).get('type', 'entry')}::{text}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(item)
        return merged[: max(limit, len(habit_results)) + len(graph_results)]

    async def inject_into_prompt(self, base_messages: list[dict]) -> list[dict]:
        """Prepends memory context to the prompt using the latest user message as the query."""
        if not base_messages:
            return []
        query = base_messages[-1].get("content", "")
        context = await self.retrieve_context(query)
        lessons = await self.self_improvement.retrieve_lessons(query)
        if not context and not lessons:
            return list(base_messages)

        messages_to_prepend = []
        lines = []
        for item in context:
            text = item.get("text")
            if not text:
                continue
            metadata = item.get("metadata", {})
            prefix = metadata.get("type") or metadata.get("role", "memory")
            lines.append(f"- [{prefix}] {text}")
        if lines:
            messages_to_prepend.append(
                {
                    "role": "system",
                    "content": "Relevant memory context:\n" + "\n".join(lines),
                }
            )

        lesson_lines = []
        hint_lines = []
        for item in lessons:
            classification = item.get("classification", "lesson")
            lesson = item.get("lesson", "")
            if lesson:
                lesson_lines.append(f"- [{classification}] {lesson}")
            for hint in item.get("hints", []):
                hint_type = hint.get("type", "hint")
                hint_value = hint.get("value", "")
                hint_reason = hint.get("reason", "")
                if hint_value:
                    if hint_type == "chain" and hint.get("chain"):
                        strength = hint.get("strength", "1")
                        domain = hint.get("domain", "general")
                        hint_lines.append(
                            f"- [{hint_type}] {hint_value}: {hint_reason} Preferred order: {hint['chain']} Strength: {strength} Domain: {domain}"
                        )
                    else:
                        hint_lines.append(f"- [{hint_type}] {hint_value}: {hint_reason}")
        if lesson_lines:
            messages_to_prepend.append(
                {
                    "role": "system",
                    "content": "Relevant lessons from past interactions:\n" + "\n".join(lesson_lines),
                }
            )
        if hint_lines:
            messages_to_prepend.append(
                {
                    "role": "system",
                    "content": "Reusable planning hints:\n" + "\n".join(hint_lines),
                }
            )

        return [*messages_to_prepend, *base_messages]

    async def learn_habit(self, trigger: str, action: str) -> None:
        """Store a behavioral pattern for future prediction."""
        habit = {
            "id": str(uuid4()),
            "trigger": trigger,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.long.save_habit(habit)
        await self.vectors.add(
            text=f"habit: when {trigger}, do {action}",
            metadata={"type": "habit", "trigger": trigger, "action": action},
            doc_id=habit["id"],
        )
        await self.graph.add_relation(trigger.lower(), action.lower(), relationship="habit")

    async def record_interaction(
        self,
        *,
        user_input: str,
        response: str = "",
        status: str,
        latency_seconds: float,
        action_summary: str = "",
        error_message: str = "",
        satisfaction: str = "unknown",
        timing_breakdown: dict[str, float] | None = None,
    ) -> dict:
        """Persist a completed interaction for later reflection."""
        return await self.self_improvement.record_interaction(
            user_input=user_input,
            response=response,
            status=status,
            latency_seconds=latency_seconds,
            action_summary=action_summary,
            error_message=error_message,
            satisfaction=satisfaction,
            timing_breakdown=timing_breakdown,
        )

    async def read_interactions(self, limit: int | None = None) -> list[dict]:
        """Expose recent interaction history to future reflection passes."""
        return await self.self_improvement.read_interactions(limit=limit)

    async def read_reflections(self, limit: int | None = None) -> list[dict]:
        """Expose reflections derived from prior interactions."""
        return await self.self_improvement.read_reflections(limit=limit)

    async def get_planning_hints(self, query: str, limit: int | None = None) -> list[dict]:
        """Return flattened structured hints relevant to a new task."""
        lessons = await self.self_improvement.retrieve_lessons(query, limit=limit)
        hints: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for lesson in lessons:
            for hint in lesson.get("hints", []):
                key = (hint.get("type", ""), hint.get("value", ""))
                if key in seen:
                    continue
                seen.add(key)
                hints.append(dict(hint))
        hints.sort(key=self._hint_rank, reverse=True)
        return hints

    def _hint_rank(self, hint: dict) -> tuple[int, int]:
        """Prefer stronger chain hints, then keep general hints in stable priority buckets."""
        hint_type = hint.get("type", "")
        if hint_type == "chain":
            return (3, int(hint.get("strength", "1")))
        if hint_type in {"reliability", "risk"}:
            return (2, 0)
        return (1, 0)

    async def _matching_habits(self, query: str) -> list[dict]:
        """Finds habits that match the current query."""
        query_lower = query.lower()
        habits = await self.long.read_habits()
        matches: list[dict] = []
        for habit in habits:
            trigger = habit.get("trigger", "").lower()
            action = habit.get("action", "")
            if trigger and (trigger in query_lower or query_lower in trigger):
                matches.append(
                    {
                        "text": f"When {habit['trigger']}, do {action}",
                        "metadata": {
                            "type": "habit",
                            "trigger": habit["trigger"],
                            "action": action,
                        },
                    }
                )
        return matches[: self.habit_limit]

    async def _graph_context(self, query: str) -> list[dict]:
        """Builds lightweight graph-derived context for mentioned entities."""
        results: list[dict] = []
        for token in self._extract_entities(query):
            relations = await self.graph.describe(token.lower())
            for relation in relations:
                results.append(
                    {
                        "text": f"{relation['source']} {relation['relationship']} {relation['target']}",
                        "metadata": {"type": "graph"},
                    }
                )
        return results

    async def _index_graph(self, entry: dict) -> None:
        """Indexes simple graph relations from roles, tags, and named entities."""
        role = entry.get("role", "").lower()
        tags = [tag.lower() for tag in entry.get("tags", [])]
        for tag in tags:
            await self.graph.add_relation(role, tag, relationship="tagged")

        entities = self._extract_entities(entry.get("content", ""))
        for entity in entities:
            await self.graph.add_relation(role, entity.lower(), relationship="mentioned")
            for tag in tags:
                await self.graph.add_relation(entity.lower(), tag, relationship="tagged")

    def _extract_entities(self, text: str) -> list[str]:
        """Extracts simple entity-like tokens from a text snippet."""
        entities = set(re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", text))
        return sorted(entities)
