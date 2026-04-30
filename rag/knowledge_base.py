"""Load pet-care markdown docs and split them into retrievable chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    """One retrievable chunk of pet-care knowledge."""

    source: str       # filename, e.g. "dogs_general.md"
    title: str        # h1 of the source doc
    section: str      # h2 within the doc, "" if none
    text: str         # chunk body
    chunk_id: int     # unique id within the corpus

    def citation(self) -> str:
        """Short label used in answer citations and logs."""
        if self.section:
            return f"{self.source} § {self.section}"
        return self.source

    def for_embedding(self) -> str:
        """Text representation given to the embedder.

        Prepending the title and section gives the embedder semantic
        anchors so a query like 'how often to bathe a dog' matches the
        'Bath frequency' section even when the body itself doesn't repeat
        those words.
        """
        header = self.title
        if self.section:
            header = f"{self.title} — {self.section}"
        return f"{header}\n\n{self.text}"


def _split_by_h2(markdown: str) -> list[tuple[str, str, str]]:
    """Split markdown into (title, section, body) triples by ## headers."""
    lines = markdown.splitlines()
    title = ""
    sections: list[tuple[str, str, list[str]]] = []
    current_section = ""
    buffer: list[str] = []

    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            if buffer:
                sections.append((title, current_section, buffer))
            current_section = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        sections.append((title, current_section, buffer))

    return [
        (t, s, "\n".join(buf).strip())
        for t, s, buf in sections
        if "\n".join(buf).strip()
    ]


def load_documents(knowledge_dir: Path) -> list[Document]:
    """Load every .md file in knowledge_dir as one or more Document chunks."""
    knowledge_dir = Path(knowledge_dir)
    if not knowledge_dir.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")

    docs: list[Document] = []
    chunk_id = 0
    for md_file in sorted(knowledge_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for title, section, body in _split_by_h2(text):
            docs.append(Document(
                source=md_file.name,
                title=title,
                section=section,
                text=body,
                chunk_id=chunk_id,
            ))
            chunk_id += 1
    return docs
