"""Gemini API client and prompt templates for grounded generation."""

from __future__ import annotations

import os


SYSTEM_INSTRUCTION = """You are PawPal, a careful pet-care assistant.

Rules you must follow:
- Answer using ONLY the provided context passages. Never invent facts beyond them.
- If the context does not clearly cover the question, say so plainly and recommend asking a vet.
- Be concise: 2 to 5 sentences for most answers, 4 to 7 for schedule explanations.
- Never give medical diagnoses. For health concerns, always recommend a vet visit.
- End every answer with a citation line in the form: [Sources: file1.md, file2.md]
"""

QA_TEMPLATE = """Context passages:
{context}

User question: {question}

Answer using only the context above. End with the [Sources: ...] line."""

EXPLAIN_TEMPLATE = """Context passages:
{context}

The user has the following daily pet-care schedule:
{schedule}

In 4 to 7 sentences, explain why this schedule is reasonable, citing the
context. Mention any concerns you notice (medication timing conflicts,
exercise too close to meals, gaps too long for the species, etc.) if they
appear in the context. End with the [Sources: ...] line."""


class GeneratorError(Exception):
    """Raised when the LLM call fails or is misconfigured."""


class Generator:
    """Thin wrapper around the Gemini API.

    The API key is read from GEMINI_API_KEY at construction time. The
    model name defaults to gemini-2.0-flash, which is on Google's free
    tier as of writing.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key: str | None = None,
    ):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeneratorError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise GeneratorError(
                "google-genai is not installed. Run: pip install -r requirements.txt"
            ) from e
        self._types = types
        self.client = genai.Client(api_key=key)
        self.model_name = model_name
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def _generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._config,
            )
        except Exception as e:
            raise GeneratorError(f"Gemini API call failed: {e}") from e
        text = getattr(response, "text", None)
        if not text:
            raise GeneratorError("Gemini returned an empty response.")
        return text.strip()

    def answer_question(self, question: str, contexts: list[str]) -> str:
        if not contexts:
            return (
                "The knowledge base doesn't cover this clearly — "
                "I'd recommend asking a vet."
            )
        context_block = "\n\n---\n\n".join(contexts)
        return self._generate(
            QA_TEMPLATE.format(context=context_block, question=question)
        )

    def explain_schedule(self, schedule_text: str, contexts: list[str]) -> str:
        if not contexts:
            return (
                "The knowledge base doesn't cover scheduling principles for "
                "these tasks. The schedule is structurally OK, but I can't "
                "speak to its appropriateness for your pets."
            )
        context_block = "\n\n---\n\n".join(contexts)
        return self._generate(
            EXPLAIN_TEMPLATE.format(context=context_block, schedule=schedule_text)
        )
