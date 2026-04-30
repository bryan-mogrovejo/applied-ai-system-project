"""Confidence scoring for RAG responses.

The score is derived from retrieval similarity, not from the LLM's own
self-rating. Reason: the LLM has already been told to ground its answer
in the context, so a weak retrieval IS a weak answer regardless of how
fluent the generated text sounds.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.retriever import RetrievalResult


HIGH_THRESHOLD = 0.55  # cosine similarity above which the top match is considered solid
LOW_THRESHOLD = 0.35   # below this, the answer is probably guessing


@dataclass
class ConfidenceScore:
    score: float       # the top-1 retrieval similarity, [0, 1]
    label: str         # "high" | "medium" | "low"
    reasoning: str     # short human-readable explanation

    def display(self) -> str:
        return f"{self.label.capitalize()} confidence ({self.score:.2f})"


def score_retrieval(results: list[RetrievalResult]) -> ConfidenceScore:
    """Map retrieval results to a confidence label.

    Uses the top-1 cosine score as the headline number. A future version
    could also weight the gap between top-1 and top-2 (a wide gap means
    one strong match; a narrow gap means several weak ones), but the
    single-number version is easier for users to interpret.
    """
    if not results:
        return ConfidenceScore(
            score=0.0,
            label="low",
            reasoning="No relevant context found in the knowledge base.",
        )

    top = results[0].score
    if top >= HIGH_THRESHOLD:
        return ConfidenceScore(
            score=top,
            label="high",
            reasoning=f"Strong match in knowledge base (top similarity {top:.2f}).",
        )
    if top >= LOW_THRESHOLD:
        return ConfidenceScore(
            score=top,
            label="medium",
            reasoning=(
                f"Partial match in knowledge base (top similarity {top:.2f}); "
                f"answer may be incomplete."
            ),
        )
    return ConfidenceScore(
        score=top,
        label="low",
        reasoning=(
            f"Weak match in knowledge base (top similarity {top:.2f}); "
            f"treat the answer with caution and consider asking a vet."
        ),
    )
