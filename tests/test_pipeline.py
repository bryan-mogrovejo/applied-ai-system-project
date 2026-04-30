"""Pipeline tests — mocks the Gemini generator to stay free and offline."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag.embedder import Embedder
from rag.generator import GeneratorError
from rag.pipeline import RAGPipeline


KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


class FakeGenerator:
    """Replaces the real Gemini client. Records calls, returns canned text."""

    def __init__(self, response: str = "Test answer. [Sources: dogs_general.md]"):
        self._response = response
        self.calls: list[tuple[str, str, list[str]]] = []

    def answer_question(self, question, contexts):
        self.calls.append(("answer_question", question, list(contexts)))
        return self._response

    def explain_schedule(self, schedule_text, contexts):
        self.calls.append(("explain_schedule", schedule_text, list(contexts)))
        return self._response


class FailingGenerator:
    """Raises GeneratorError on any call — used to test error handling."""

    def answer_question(self, question, contexts):
        raise GeneratorError("simulated API failure")

    def explain_schedule(self, schedule_text, contexts):
        raise GeneratorError("simulated API failure")


@pytest.fixture(scope="module")
def real_embedder():
    """Load the real sentence-transformer once for all pipeline tests.

    First run downloads ~80MB; subsequent runs use the local cache.
    """
    return Embedder()


@pytest.fixture
def pipeline(tmp_path, real_embedder):
    log_path = tmp_path / "rag.jsonl"
    return RAGPipeline(
        knowledge_dir=KNOWLEDGE_DIR,
        log_path=log_path,
        embedder=real_embedder,
        generator=FakeGenerator(),
    )


def test_ask_returns_answer_citations_and_confidence(pipeline):
    response = pipeline.ask("How often should I walk my dog?")
    assert response.error is None
    assert response.answer.startswith("Test answer")
    assert len(response.citations) > 0
    assert response.confidence.label in {"high", "medium", "low"}
    assert len(response.retrieval) > 0


def test_ask_empty_question_returns_validation_error(pipeline):
    response = pipeline.ask("")
    assert response.error == "Please enter a question."
    assert response.answer == "Please enter a question."


def test_ask_oversized_question_returns_validation_error(pipeline):
    response = pipeline.ask("x" * 5000)
    assert response.error is not None
    assert "too long" in response.error


def test_explain_empty_schedule_returns_friendly_message(pipeline):
    response = pipeline.explain_schedule([])
    assert response.error == "empty_schedule"
    assert "add some tasks" in response.answer.lower()


def test_explain_schedule_calls_generator_with_full_text(pipeline):
    schedule = [
        {"time": "07:00", "pet": "Rex",  "task": "Feed",         "duration": "10 min", "priority": "high"},
        {"time": "08:00", "pet": "Rex",  "task": "Morning walk", "duration": "30 min", "priority": "high"},
    ]
    response = pipeline.explain_schedule(schedule)
    assert response.error is None
    assert response.answer.startswith("Test answer")

    # Generator should have been called with a schedule text containing both tasks
    fake = pipeline._generator
    assert isinstance(fake, FakeGenerator)
    last_call = fake.calls[-1]
    assert last_call[0] == "explain_schedule"
    assert "Morning walk" in last_call[1]


def test_pipeline_logs_event_to_jsonl(tmp_path, real_embedder):
    log_path = tmp_path / "rag.jsonl"
    p = RAGPipeline(
        knowledge_dir=KNOWLEDGE_DIR,
        log_path=log_path,
        embedder=real_embedder,
        generator=FakeGenerator(),
    )
    p.ask("Can my cat eat tuna?")
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["kind"] == "ask"
    assert event["question"] == "Can my cat eat tuna?"
    assert "confidence" in event
    assert "retrieval" in event


def test_pipeline_handles_generator_error_gracefully(tmp_path, real_embedder):
    p = RAGPipeline(
        knowledge_dir=KNOWLEDGE_DIR,
        log_path=tmp_path / "rag.jsonl",
        embedder=real_embedder,
        generator=FailingGenerator(),
    )
    response = p.ask("Why do dogs need exercise?")
    assert response.error is not None
    assert "simulated API failure" in response.error
    assert "couldn't reach" in response.answer.lower()
