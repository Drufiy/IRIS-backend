"""Vector-style semantic retrieval with optional local fallbacks."""

from __future__ import annotations

from collections import Counter
import math


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def _cosine_similarity(left: str, right: str) -> float:
    left_counts = Counter(_tokenize(left))
    right_counts = Counter(_tokenize(right))
    if not left_counts or not right_counts:
        return 0.0

    shared = set(left_counts) & set(right_counts)
    numerator = sum(left_counts[token] * right_counts[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class VectorStore:
    """Semantic document storage with an in-memory fallback backend."""

    def __init__(self, persist_path: str = ".chroma", embedding_model: str = "BAAI/bge-m3"):
        self.persist_path = persist_path
        self.embedding_model = embedding_model
        self._documents: list[dict] = []

    async def add(self, text: str, metadata: dict, doc_id: str) -> None:
        """Stores a document in the fallback memory backend."""
        self._documents.append(
            {
                "id": doc_id,
                "text": text,
                "metadata": metadata,
            }
        )

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Returns the closest matching documents."""
        ranked = sorted(
            self._documents,
            key=lambda item: _cosine_similarity(query, item["text"]),
            reverse=True,
        )
        return ranked[:top_k]
