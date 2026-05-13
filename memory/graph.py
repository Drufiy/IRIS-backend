"""Knowledge graph helpers."""

from __future__ import annotations


class KnowledgeGraph:
    """Minimal relationship graph for entities and workflows."""

    def __init__(self):
        self._edges: dict[str, set[str]] = {}
        self._relationships: dict[tuple[str, str], str] = {}

    async def add_relation(self, source: str, target: str, relationship: str = "related") -> None:
        """Adds a directional relationship between two nodes."""
        self._edges.setdefault(source, set()).add(target)
        self._edges.setdefault(target, set())
        self._relationships[(source, target)] = relationship

    async def neighbors(self, node: str, relationship: str | None = None) -> list[str]:
        """Returns adjacent nodes for a source entity."""
        neighbors = sorted(self._edges.get(node, set()))
        if relationship is None:
            return neighbors
        return [
            neighbor
            for neighbor in neighbors
            if self._relationships.get((node, neighbor)) == relationship
        ]

    async def describe(self, node: str) -> list[dict[str, str]]:
        """Returns structured relationship descriptions for a node."""
        descriptions: list[dict[str, str]] = []
        for neighbor in sorted(self._edges.get(node, set())):
            descriptions.append(
                {
                    "source": node,
                    "target": neighbor,
                    "relationship": self._relationships.get((node, neighbor), "related"),
                }
            )
        return descriptions
