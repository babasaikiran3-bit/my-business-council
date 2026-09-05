"""Small local retrieval subsystem with no model or database dependency."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class DocumentChunk:
    text: str
    source: str
    chunk_index: int


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into deterministic overlapping character chunks."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and overlap must be smaller")
    normalized = re.sub(r"\s+", " ", text).strip()
    step = size - overlap
    return [normalized[start : start + size] for start in range(0, len(normalized), step)]


def ingest_documents(
    directory: str | Path, size: int = 800, overlap: int = 100
) -> list[DocumentChunk]:
    """Read supported local text documents and return chunked source records."""
    root = Path(directory)
    if not root.exists():
        return []
    chunks: list[DocumentChunk] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".markdown"}:
            text = path.read_text(encoding="utf-8")
            chunks.extend(
                DocumentChunk(chunk, str(path), index)
                for index, chunk in enumerate(chunk_text(text, size, overlap))
                if chunk
            )
    return chunks


def _vector(text: str) -> dict[str, float]:
    tokens = TOKEN_RE.findall(text.lower())
    counts: dict[str, float] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0.0) + 1.0
    return counts


def _similarity(left: dict[str, float], right: dict[str, float]) -> float:
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    magnitude = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return dot / magnitude if magnitude else 0.0


class LocalRetriever:
    """In-memory lexical embedding index suitable for small local document sets."""

    def __init__(
        self,
        chunks: Iterable[DocumentChunk],
        reranker: Optional[Callable[[str, DocumentChunk], float]] = None,
    ):
        self.chunks = list(chunks)
        self._vectors = [_vector(chunk.text) for chunk in self.chunks]
        self.reranker = reranker

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        if top_k <= 0:
            return []
        query_vector = _vector(query)
        scored = [
            (self.reranker(query, chunk) if self.reranker else _similarity(query_vector, vector), chunk)
            for chunk, vector in zip(self.chunks, self._vectors)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "text": chunk.text,
                "source": chunk.source,
                "chunk_index": chunk.chunk_index,
                "score": round(float(score), 4),
            }
            for score, chunk in scored[:top_k]
            if score > 0
        ]


def retrieve_context(
    query: str, directory: str | Path, top_k: int = 3, size: int = 800, overlap: int = 100
) -> tuple[str, list[dict[str, object]]]:
    """Return citation-ready context and retrieval metadata."""
    results = LocalRetriever(ingest_documents(directory, size, overlap)).retrieve(query, top_k)
    context = "\n\n".join(
        f"[Source {index}: {item['source']}]\n{item['text']}"
        for index, item in enumerate(results, 1)
    )
    return context, results
