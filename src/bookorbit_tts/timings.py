"""Word timings for BookOrbit's captioned-speech response.

Piper already decides how long each phoneme lasts. Grouping those phonemes
back into words does not run another model. When a voice has no phoneme
times, the audio duration is split across the words by length.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(r"\S+")
# Phonemes that are punctuation rather than a spoken word of their own.
_PUNCTUATION = set("!'(),-.:;?")


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


def timings_from_duration(text: str, duration: float) -> tuple[WordTiming, ...]:
    """Split ``duration`` across the words in ``text``."""
    tokens = list(_TOKEN.finditer(text))
    if not tokens or duration <= 0:
        return ()
    weights = [max(1, len(match.group(0))) for match in tokens]
    total = sum(weights)
    start = 0.0
    result: list[WordTiming] = []
    for match, weight in zip(tokens, weights):
        end = start + duration * weight / total
        result.append(WordTiming(match.group(0), start, end))
        start = end
    last = result[-1]
    result[-1] = WordTiming(last.word, last.start, duration)
    return tuple(result)


def timings_from_alignments(
    text: str,
    alignments: list[tuple[str, int]],
    sample_rate: int,
) -> tuple[WordTiming, ...]:
    """Map Piper phoneme alignments onto the words of ``text``.

    ``alignments`` is ``(phoneme, sample_count)`` in order. ``^`` and ``$``
    are the start and end markers Piper inserts. A space phoneme separates
    words. If the groups do not line up with the text, fall back to splitting
    the whole clip by word length.
    """
    if sample_rate <= 0:
        return ()
    tokens = [match.group(0) for match in _TOKEN.finditer(text)]
    if not tokens:
        return ()

    cursor = 0
    groups: list[tuple[int, int, bool]] = []
    group_start: int | None = None
    group_spoken = False
    for phoneme, count in alignments:
        count = max(0, int(count))
        if phoneme in {"^", "$", " "}:
            if group_start is not None:
                groups.append((group_start, cursor, group_spoken))
                group_start = None
                group_spoken = False
            cursor += count
            continue
        if group_start is None:
            group_start = cursor
        if phoneme not in _PUNCTUATION:
            group_spoken = True
        cursor += count
    if group_start is not None:
        groups.append((group_start, cursor, group_spoken))

    spoken = [(start, end) for start, end, is_spoken in groups if is_spoken]
    # A punctuation-only group belongs to the word beside it.
    if len(spoken) != len(groups):
        spoken = _merge_punctuation(groups)
    if cursor <= 0 or len(spoken) != len(tokens):
        return timings_from_duration(text, cursor / sample_rate)

    spoken[0] = (0, spoken[0][1])
    spoken[-1] = (spoken[-1][0], cursor)
    return tuple(
        WordTiming(word, start / sample_rate, end / sample_rate)
        for word, (start, end) in zip(tokens, spoken)
    )


def _merge_punctuation(groups: list[tuple[int, int, bool]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end, is_spoken in groups:
        if is_spoken or not merged:
            merged.append((start, end))
            continue
        previous_start, _ = merged[-1]
        merged[-1] = (previous_start, end)
    return [(start, end) for start, end in merged if end > start]
