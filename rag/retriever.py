"""Cosine-similarity vector retrieval over a fixed document corpus."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rag.embedder import DEFAULT_DIM, Embedder
from rag.knowledge_base import Document


@dataclass
class RetrievalResult:
    document: Document
    score: float  # cosine similarity in [-1, 1], typically [0, 1] for normalized text


class Retriever:
    """In-memory vector index with cosine-similarity top-k search.

    The whole corpus is small (~50 chunks) so a numpy dot product
    against a stacked matrix is faster and simpler than FAISS.
    """

    def __init__(self, embedder: Embedder, documents: list[Document]):
        self.embedder = embedder
        self.documents = documents
        self._matrix: np.ndarray | None = None

    def index(self) -> None:
        """Compute and cache embeddings for the full corpus."""
        if self._matrix is not None:
            return
        if not self.documents:
            self._matrix = np.zeros((0, DEFAULT_DIM), dtype=np.float32)
            return
        texts = [d.for_embedding() for d in self.documents]
        self._matrix = self.embedder.embed(texts)

    def retrieve(self, query: str, k: int = 4) -> list[RetrievalResult]:
        """Return the top-k most similar documents to the query.

        Empty / whitespace queries return an empty list rather than
        raising — callers (the pipeline) handle the user-facing error.
        """
        if not query or not query.strip() or not self.documents:
            return []
        if self._matrix is None:
            self.index()

        q_vec = self.embedder.embed([query])[0]   # shape (d,)
        scores = self._matrix @ q_vec             # vectors are L2-normalized → dot = cosine
        top_idx = np.argsort(-scores)[:k]
        return [
            RetrievalResult(document=self.documents[i], score=float(scores[i]))
            for i in top_idx
        ]
