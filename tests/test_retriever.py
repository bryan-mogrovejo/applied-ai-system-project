"""Unit tests for the retriever — uses a fake embedder for speed."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag.knowledge_base import Document
from rag.retriever import Retriever


class FakeEmbedder:
    """Deterministic embedder that maps each input to a fixed vector.

    Lets retriever tests run without downloading the real model.
    """

    def __init__(self, vectors_by_text: dict[str, np.ndarray], dim: int = 3):
        self._vectors = vectors_by_text
        self.dim = (
            next(iter(vectors_by_text.values())).shape[0]
            if vectors_by_text else dim
        )

    def embed(self, texts):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        rows = []
        for t in texts:
            if t in self._vectors:
                rows.append(self._vectors[t])
            else:
                # default to a zero-ish vector that won't match anything strongly
                rows.append(np.full(self.dim, 0.01, dtype=np.float32))
        return np.stack(rows).astype(np.float32)


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _make_docs() -> list[Document]:
    return [
        Document(source="dogs.md",  title="Dogs",  section="walks", text="dogs need daily walks", chunk_id=0),
        Document(source="cats.md",  title="Cats",  section="food",  text="cats need fresh water",  chunk_id=1),
        Document(source="birds.md", title="Birds", section="cage",  text="birds need cage time",   chunk_id=2),
    ]


def _make_retriever() -> Retriever:
    docs = _make_docs()
    # craft a vector space where each doc has a clearly distinct direction
    # and known queries align with one of them
    vec_dog  = _normalize(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    vec_cat  = _normalize(np.array([0.0, 1.0, 0.0], dtype=np.float32))
    vec_bird = _normalize(np.array([0.0, 0.0, 1.0], dtype=np.float32))

    vectors = {
        docs[0].for_embedding(): vec_dog,
        docs[1].for_embedding(): vec_cat,
        docs[2].for_embedding(): vec_bird,
        "how often should I walk my dog": vec_dog,
        "what do cats drink":              vec_cat,
        "do birds need exercise":          vec_bird,
    }
    return Retriever(FakeEmbedder(vectors), docs)


def test_retriever_finds_matching_dog_doc():
    r = _make_retriever()
    results = r.retrieve("how often should I walk my dog", k=1)
    assert len(results) == 1
    assert results[0].document.source == "dogs.md"
    assert results[0].score > 0.99  # near-perfect cosine alignment


def test_retriever_top_k_respected():
    r = _make_retriever()
    results = r.retrieve("how often should I walk my dog", k=2)
    assert len(results) == 2
    # top-1 should still be dogs.md
    assert results[0].document.source == "dogs.md"


def test_retriever_orders_by_similarity():
    r = _make_retriever()
    results = r.retrieve("how often should I walk my dog", k=3)
    scores = [res.score for res in results]
    assert scores == sorted(scores, reverse=True)


def test_retriever_empty_query_returns_empty():
    r = _make_retriever()
    assert r.retrieve("") == []
    assert r.retrieve("   ") == []


def test_retriever_no_documents_returns_empty():
    empty = Retriever(FakeEmbedder({}), documents=[])
    assert empty.retrieve("anything") == []


def test_retriever_indexes_only_once():
    r = _make_retriever()
    r.index()
    matrix_first = r._matrix
    r.index()  # second call should be a no-op
    assert r._matrix is matrix_first
