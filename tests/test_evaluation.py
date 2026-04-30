"""Retrieval evaluation suite — measures accuracy on a fixed Q&A set.

For each question, we know which source file SHOULD be retrieved. The
test passes if at least 80% of questions retrieve their expected source
in the top-3 results. This is the project's reliability metric for the
RAG layer.

Note: this only evaluates retrieval, not generation. The Gemini layer
is not tested here because (1) it costs API calls and (2) the LLM is
constrained by the system prompt to answer only from retrieved
context — so a strong retrieval implies a grounded answer.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag.embedder import Embedder
from rag.knowledge_base import load_documents
from rag.retriever import Retriever


KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

# Each item: question + the source file we expect to appear in the top-3 results.
GOLDEN_QUESTIONS = [
    {"question": "How often should I bathe a short-haired dog?",
     "expected_source": "grooming.md"},
    {"question": "What human foods are toxic to cats?",
     "expected_source": "nutrition.md"},
    {"question": "When should I start house-training a puppy?",
     "expected_source": "puppy_kitten.md"},
    {"question": "How do I introduce two cats safely?",
     "expected_source": "behavior_cats.md"},
    {"question": "How long should I walk a senior dog?",
     "expected_source": "senior_pets.md"},
    {"question": "What are signs of a urinary blockage in cats?",
     "expected_source": "health_signs.md"},
    {"question": "How much exercise does a Border Collie need?",
     "expected_source": "breeds.md"},
    {"question": "What should I feed a pet rabbit?",
     "expected_source": "small_pets.md"},
    {"question": "Should I give thyroid medication with food?",
     "expected_source": "medications.md"},
    {"question": "Why are morning walks before breakfast a good idea?",
     "expected_source": "scheduling_principles.md"},
]

PASS_THRESHOLD = 0.80  # fraction of questions that must hit the expected source in top-3
TOP_K = 3


@pytest.fixture(scope="module")
def retriever():
    embedder = Embedder()
    docs = load_documents(KNOWLEDGE_DIR)
    r = Retriever(embedder, docs)
    r.index()
    return r


def test_golden_questions_meet_accuracy_threshold(retriever):
    """Aggregate accuracy: at least PASS_THRESHOLD of questions retrieve their expected source."""
    hits = 0
    misses: list[tuple[str, str, list[str]]] = []

    for item in GOLDEN_QUESTIONS:
        results = retriever.retrieve(item["question"], k=TOP_K)
        retrieved_sources = [r.document.source for r in results]
        if item["expected_source"] in retrieved_sources:
            hits += 1
        else:
            misses.append((item["question"], item["expected_source"], retrieved_sources))

    accuracy = hits / len(GOLDEN_QUESTIONS)
    miss_report = "\n".join(
        f"  - {q!r}\n    expected: {exp}\n    got:      {got}"
        for q, exp, got in misses
    )
    assert accuracy >= PASS_THRESHOLD, (
        f"Retrieval accuracy {accuracy:.0%} below threshold {PASS_THRESHOLD:.0%}.\n"
        f"Misses:\n{miss_report}"
    )


@pytest.mark.parametrize("item", GOLDEN_QUESTIONS, ids=[g["question"][:40] for g in GOLDEN_QUESTIONS])
def test_individual_question_retrieves_expected_source(retriever, item):
    """One assertion per question — surfaces which queries fail in pytest output."""
    results = retriever.retrieve(item["question"], k=TOP_K)
    retrieved_sources = [r.document.source for r in results]
    assert item["expected_source"] in retrieved_sources, (
        f"Expected {item['expected_source']!r} in top-{TOP_K} for question "
        f"{item['question']!r}, got {retrieved_sources}"
    )
