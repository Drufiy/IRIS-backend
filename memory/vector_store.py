"""Vector-style semantic retrieval via ChromaDB with BGE-M3 embeddings."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

# Fallback TF-IDF implementation used when ChromaDB is unavailable
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


class _FallbackStore:
    """In-memory TF-IDF fallback when ChromaDB is not available."""

    def __init__(self) -> None:
        self._documents: list[dict] = []

    def add(self, text: str, metadata: dict, doc_id: str) -> None:
        self._documents.append({"id": doc_id, "text": text, "metadata": metadata})

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        ranked = sorted(
            self._documents,
            key=lambda item: _cosine_similarity(query, item["text"]),
            reverse=True,
        )
        return ranked[:top_k]


class VectorStore:
    """Semantic document storage powered by ChromaDB + BGE-M3 embeddings.

    Falls back to an in-memory TF-IDF matcher when ChromaDB or the embedding
    model cannot be loaded (e.g. on resource-constrained machines).
    """

    def __init__(self, persist_path: str = ".chroma", embedding_model: str = "BAAI/bge-m3"):
        self.persist_path = str(Path(persist_path).expanduser())
        self.embedding_model = embedding_model
        self._chroma_collection = None
        self._fallback: _FallbackStore | None = None

    # ── lazy initialisation ──────────────────────────────────────────────

    async def _ensure_backend(self):
        """Initialise the ChromaDB backend (or fallback) on first use."""
        if self._chroma_collection is not None or self._fallback is not None:
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model,
            )
            # ChromaDB operations are synchronous – offload to a thread.
            client = await asyncio.to_thread(
                chromadb.PersistentClient,
                path=self.persist_path,
            )

            try:
                collection = await asyncio.to_thread(
                    client.get_collection,
                    name="iris_memory",
                    embedding_function=ef,
                )
            except ValueError:
                collection = await asyncio.to_thread(
                    client.create_collection,
                    name="iris_memory",
                    embedding_function=ef,
                )

            self._chroma_collection = collection
            logger.info(
                "VectorStore: ChromaDB ready (path=%s, model=%s)",
                self.persist_path,
                self.embedding_model,
            )
        except Exception as exc:
            logger.warning(
                "VectorStore: ChromaDB unavailable (%s), using TF-IDF fallback.",
                exc,
            )
            self._fallback = _FallbackStore()

    # ── public interface ─────────────────────────────────────────────────

    async def add(self, text: str, metadata: dict, doc_id: str) -> None:
        """Store a document in the vector store."""
        await self._ensure_backend()

        if self._chroma_collection is not None:
            try:
                await asyncio.to_thread(
                    self._chroma_collection.add,
                    documents=[text],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
            except Exception as exc:
                logger.warning("VectorStore add error: %s", exc)

        elif self._fallback is not None:
            self._fallback.add(text, metadata, doc_id)

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return the *top_k* closest documents to *query*.

        Each result dict contains the keys ``text``, ``metadata``, ``id``
        (and ``distance`` when ChromaDB is active).
        """
        await self._ensure_backend()

        if self._chroma_collection is not None:
            try:
                results = await asyncio.to_thread(
                    self._chroma_collection.query,
                    query_texts=[query],
                    n_results=top_k,
                )
                return self._format_chroma_results(results)
            except Exception as exc:
                logger.warning("VectorStore search error: %s", exc)
                return []

        if self._fallback is not None:
            return self._fallback.search(query, top_k)

        return []

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_chroma_results(results: dict) -> list[dict]:
        """Normalise a ChromaDB query response into the IRIS interface."""
        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        ids = results.get("ids", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []

        formatted = []
        for idx in range(len(documents)):
            formatted.append(
                {
                    "text": documents[idx],
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "id": ids[idx] if idx < len(ids) else "",
                    "distance": distances[idx] if idx < len(distances) else 0.0,
                }
            )
        return formatted
