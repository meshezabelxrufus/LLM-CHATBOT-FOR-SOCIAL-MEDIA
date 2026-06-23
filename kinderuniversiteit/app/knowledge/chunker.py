"""
Recursive character-level text splitter.

Strategy: try to split on the largest natural boundary first (paragraph →
sentence → word → character). If a piece still exceeds `chunk_size` after
splitting on the current separator, recurse with the next one. After all
pieces are within size, slide an `overlap` window between consecutive chunks
so that context at boundaries is preserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Ordered from coarsest to finest. The splitter tries each in turn.
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""]


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int


class RecursiveChunker:
    def __init__(self, chunk_size: int = 800, overlap: int = 100) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    # ── Public ────────────────────────────────────────────────────────────────

    def chunk(self, text: str) -> list[str]:
        """Split `text` into overlapping chunks, each at most `chunk_size` chars."""
        text = _normalise(text)
        if not text:
            return []
        pieces = self._split(text, _SEPARATORS)
        pieces = [p for p in pieces if p.strip()]
        return self._apply_overlap(pieces)

    def chunk_with_metadata(self, text: str) -> list[Chunk]:
        return [Chunk(text=t, index=i) for i, t in enumerate(self.chunk(text))]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split until every piece fits within `chunk_size`."""
        if len(text) <= self.chunk_size:
            return [text]

        # No more separators — hard-cut at chunk_size.
        if not separators or separators[0] == "":
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        sep, rest = separators[0], separators[1:]
        parts = text.split(sep)
        chunks: list[str] = []
        current = ""

        for part in parts:
            joined = (current + sep + part).strip() if current else part.strip()

            if len(joined) <= self.chunk_size:
                current = joined
            else:
                # Flush the accumulator.
                if current:
                    chunks.append(current)

                if len(part) > self.chunk_size:
                    # This single part is already too big — recurse deeper.
                    chunks.extend(self._split(part.strip(), rest))
                    current = ""
                else:
                    current = part.strip()

        if current:
            chunks.append(current)

        return chunks

    def _apply_overlap(self, pieces: list[str]) -> list[str]:
        """Prepend the tail of the previous chunk to each subsequent chunk."""
        if self.overlap == 0 or len(pieces) <= 1:
            return pieces

        result = [pieces[0]]
        for piece in pieces[1:]:
            tail = result[-1][-self.overlap :]
            candidate = (tail + " " + piece).strip()
            # Only add the tail if it doesn't push us significantly over the limit.
            result.append(candidate if len(candidate) <= self.chunk_size + self.overlap else piece)

        return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
