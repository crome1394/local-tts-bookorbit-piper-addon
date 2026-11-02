"""Logging helpers for noisy third-party libraries."""

from __future__ import annotations

import logging


def silence_phonemizer() -> None:
    """Stop phonemizer's word-alignment warnings from reaching the console.

    phonemizer re-creates and re-levels its logger (``phonemizer``) every time
    a backend is built, so setting a level is not enough. It does respect
    ``propagate``, which keeps the harmless "words count mismatch" warnings
    produced by Kokoro's espeak backend out of the request log.
    """
    logger = logging.getLogger("phonemizer")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
