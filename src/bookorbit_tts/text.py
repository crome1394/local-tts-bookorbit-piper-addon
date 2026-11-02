"""Text preparation before synthesis."""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
# Sentence end followed by whitespace. Keeps the punctuation with the sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"'”’)]*\s+")


def normalize(text: str) -> str:
    """Collapse whitespace and trim, without touching the words themselves."""
    return _WHITESPACE.sub(" ", text).strip()


def split_for_synthesis(text: str, max_chars: int = 600) -> list[str]:
    """Split text into sentence-aligned chunks of at most ``max_chars``.

    Long single sentences are hard-wrapped on word boundaries so a single
    request can never allocate an unbounded phoneme sequence. Keeping chunks
    near a sentence means each chunk still sounds natural.
    """
    text = normalize(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_wrap(sentence, max_chars))
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    words = text.split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        # A token with no spaces would otherwise become one unbounded chunk.
        if len(word) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for offset in range(0, len(word), max_chars):
                chunks.append(word[offset : offset + max_chars])
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks
