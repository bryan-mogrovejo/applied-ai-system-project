"""Local embedding model wrapper. Uses sentence-transformers — no API calls."""

from __future__ import annotations

import numpy as np

DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384-dim, ~80MB, fast on CPU
DEFAULT_DIM = 384


class Embedder:
    """Lazy-loaded sentence-transformer embedder.

    The model downloads on first use (~80MB) and is cached locally
    afterward. All encoding runs on CPU on the user's machine — no
    embedding API key required.

    sentence_transformers is imported inside the property so unit tests
    that pass a fake embedder can run without that dependency installed.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 matrix of L2-normalized embeddings."""
        if not texts:
            return np.zeros((0, DEFAULT_DIM), dtype=np.float32)
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)
