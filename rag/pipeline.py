"""End-to-end RAG pipeline: validate → retrieve → generate → score → log.

This is the single entry point used by the Streamlit UI. It owns the
embedder, retriever, and generator, handles input validation and
errors, and writes a structured log line for every call.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag.confidence import ConfidenceScore, score_retrieval
from rag.embedder import Embedder
from rag.generator import Generator, GeneratorError
from rag.knowledge_base import load_documents
from rag.retriever import RetrievalResult, Retriever


MAX_QUERY_LENGTH = 1000

DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "rag.jsonl"


@dataclass
class RAGResponse:
    """Everything the UI needs to display one RAG turn."""

    answer: str
    citations: list[str]
    confidence: ConfidenceScore
    retrieval: list[RetrievalResult] = field(default_factory=list)
    error: str | None = None

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "confidence": {
                "score": self.confidence.score,
                "label": self.confidence.label,
                "reasoning": self.confidence.reasoning,
            },
            "retrieval": [
                {
                    "source": r.document.source,
                    "section": r.document.section,
                    "score": round(r.score, 4),
                }
                for r in self.retrieval
            ],
            "error": self.error,
        }


class RAGPipeline:
    """Orchestrates the full retrieve-augment-generate flow."""

    def __init__(
        self,
        knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
        log_path: Path = DEFAULT_LOG_PATH,
        embedder: Embedder | None = None,
        generator: Generator | None = None,
        top_k: int = 4,
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.log_path = Path(log_path)
        self.top_k = top_k
        self.embedder = embedder or Embedder()
        self.documents = load_documents(self.knowledge_dir)
        self.retriever = Retriever(self.embedder, self.documents)
        self.retriever.index()
        self._generator = generator
        self._setup_logger()

    @property
    def generator(self) -> Generator:
        """Lazy-construct the Gemini client so unit tests can run without a key."""
        if self._generator is None:
            self._generator = Generator()
        return self._generator

    def _setup_logger(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("pawpal.rag")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("[%(asctime)s] %(levelname)s pawpal.rag: %(message)s")
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _log_event(self, event: dict[str, Any]) -> None:
        try:
            event["timestamp"] = time.time()
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            self._logger.warning(f"Failed to write log line: {e}")

    @staticmethod
    def _validate_query(query: str) -> str | None:
        if not query or not query.strip():
            return "Please enter a question."
        if len(query) > MAX_QUERY_LENGTH:
            return f"Question is too long (max {MAX_QUERY_LENGTH} characters)."
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, question: str) -> RAGResponse:
        """Answer a free-form pet-care question with grounded retrieval."""
        validation_error = self._validate_query(question)
        if validation_error:
            return RAGResponse(
                answer=validation_error,
                citations=[],
                confidence=score_retrieval([]),
                error=validation_error,
            )

        start = time.perf_counter()
        results = self.retriever.retrieve(question, k=self.top_k)
        confidence = score_retrieval(results)
        contexts = [
            f"Source: {r.document.source}\n"
            f"Section: {r.document.section or '(intro)'}\n\n"
            f"{r.document.text}"
            for r in results
        ]
        citations = sorted({r.document.source for r in results})

        try:
            answer = self.generator.answer_question(question, contexts)
            error: str | None = None
        except GeneratorError as e:
            answer = (
                "Sorry, I couldn't reach the language model right now. "
                "Please check your API key and try again."
            )
            error = str(e)
            self._logger.error(f"Generator error during ask(): {e}")

        latency = time.perf_counter() - start
        response = RAGResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            retrieval=results,
            error=error,
        )
        self._log_event({
            "kind": "ask",
            "question": question,
            "latency_seconds": round(latency, 3),
            **response.to_log_dict(),
        })
        return response

    def explain_schedule(self, schedule: list[dict[str, Any]]) -> RAGResponse:
        """Generate a grounded explanation of a daily pet-care schedule."""
        if not schedule:
            return RAGResponse(
                answer="No schedule to explain — add some tasks first.",
                citations=[],
                confidence=score_retrieval([]),
                error="empty_schedule",
            )

        schedule_text = "\n".join(
            f"- {row['time']} {row['pet']}: {row['task']} "
            f"({row['duration']}, {row['priority']} priority)"
            for row in schedule
        )

        start = time.perf_counter()
        # Bias retrieval toward scheduling principles by prefixing the query
        retrieval_query = (
            "Why is this pet care daily schedule structured this way?\n"
            + schedule_text
        )
        results = self.retriever.retrieve(retrieval_query, k=self.top_k)
        confidence = score_retrieval(results)
        contexts = [
            f"Source: {r.document.source}\n"
            f"Section: {r.document.section or '(intro)'}\n\n"
            f"{r.document.text}"
            for r in results
        ]
        citations = sorted({r.document.source for r in results})

        try:
            answer = self.generator.explain_schedule(schedule_text, contexts)
            error: str | None = None
        except GeneratorError as e:
            answer = (
                "Sorry, I couldn't reach the language model right now. "
                "Please check your API key and try again."
            )
            error = str(e)
            self._logger.error(f"Generator error during explain_schedule(): {e}")

        latency = time.perf_counter() - start
        response = RAGResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            retrieval=results,
            error=error,
        )
        self._log_event({
            "kind": "explain_schedule",
            "schedule": schedule,
            "latency_seconds": round(latency, 3),
            **response.to_log_dict(),
        })
        return response
