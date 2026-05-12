"""Knowledge graph helpers."""

from __future__ import annotations


class KnowledgeGraph:
    """Minimal relationship graph for entities and workflows."""

    def __init__(self):
        self._edges: dict[str, set[str]] = {}

    async def add_relation(self, source: str, target: str) -> None:
        """Adds a directional relationship between two nodes."""
        self._edges.setdefault(source, set()).add(target)
        self._edges.setdefault(target, set())

    async def neighbors(self, node: str) -> list[str]:
        """Returns adjacent nodes for a source entity."""
        return sorted(self._edges.get(node, set()))
