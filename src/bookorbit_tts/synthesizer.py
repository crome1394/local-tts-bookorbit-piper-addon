"""Request-level synthesis: voice validation, chunking, cache, concurrency."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict

from .audio import AudioData, AudioError, concat, encode
from .config import DEFAULT_KOKORO_VOICE, DEFAULT_PIPER_VOICE, VOICE_ID, Settings
from .engines.base import Engine, Voice
from .text import normalize, split_for_synthesis
from .timings import WordTiming, timings_from_duration

log = logging.getLogger(__name__)


class SynthesisError(Exception):
    """Bad request: unknown voice, unsupported format, text too long."""


class ServerBusy(Exception):
    """Every synthesis slot is taken and the wait queue is full or expired."""


class _Gate:
    """Limit how many requests synthesize at once, and how many may wait.

    Callers past the queue are rejected immediately so a flood cannot pin
    every worker thread for the whole wait timeout.
    """

    def __init__(self, concurrency: int, max_waiting: int) -> None:
        self._concurrency = concurrency
        self._max_waiting = max_waiting
        self._active = 0
        self._waiting = 0
        self._condition = threading.Condition()

    def acquire(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        with self._condition:
            if self._active >= self._concurrency and self._waiting >= self._max_waiting:
                raise ServerBusy("synthesis queue is full")
            self._waiting += 1
            try:
                while self._active >= self._concurrency:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ServerBusy("timed out waiting for synthesis")
                    self._condition.wait(remaining)
            finally:
                self._waiting -= 1
            self._active += 1

    def release(self) -> None:
        with self._condition:
            if self._active:
                self._active -= 1
            self._condition.notify_all()


class Synthesizer:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine = engine
        self.settings = settings
        self._gate = _Gate(settings.concurrency, settings.queue)
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_words: dict[str, tuple[WordTiming, ...]] = {}
        self._cache_bytes = 0
        self._cache_lock = threading.Lock()
        self._voices: dict[str, Voice] = {voice.id: voice for voice in engine.voices()}
        self._default_voice = self._pick_default(settings, engine)

    @staticmethod
    def _pick_default(settings: Settings, engine: Engine) -> str:
        voices = engine.voices()
        if not voices:
            raise RuntimeError(f"engine {engine.name} has no usable voices")
        preferred = {
            "kokoro": DEFAULT_KOKORO_VOICE,
            "piper": DEFAULT_PIPER_VOICE,
            "espeak": "en-us",
        }.get(engine.name)
        for candidate in (settings.default_voice, preferred):
            if candidate and any(voice.id == candidate for voice in voices):
                return candidate
        return voices[0].id

    def voices(self) -> list[Voice]:
        return list(self._voices.values())

    def describe(self) -> dict:
        return {
            "engine": self.engine.name,
            "default_voice": self._default_voice,
            "voices": len(self._voices),
            "concurrency": self.settings.concurrency,
        }

    def speak(self, text: str, voice: str | None, speed: float, fmt: str) -> bytes:
        payload, _words = self._speak(text, voice, speed, fmt, captioned=False)
        return payload

    def speak_captioned(
        self, text: str, voice: str | None, speed: float, fmt: str
    ) -> tuple[bytes, tuple[WordTiming, ...]]:
        """Audio plus the time each word is spoken.

        BookOrbit uses this for word highlighting. The synthesis is the same
        work as ``speak``; the timings come from phoneme lengths when the
        engine has them.
        """
        return self._speak(text, voice, speed, fmt, captioned=True)

    def _speak(
        self, text: str, voice: str | None, speed: float, fmt: str, captioned: bool
    ) -> tuple[bytes, tuple[WordTiming, ...]]:
        text = normalize(text)
        if not text:
            raise SynthesisError("input text is empty")
        if len(text) > self.settings.max_text_chars:
            raise SynthesisError(
                f"text is {len(text)} characters; the limit is {self.settings.max_text_chars}"
            )
        fmt = (fmt or "mp3").lower()
        voice = voice or self._default_voice
        if not VOICE_ID.fullmatch(voice):
            raise SynthesisError("invalid voice id")
        if voice not in self._voices:
            known = ", ".join(sorted(self._voices)[:8])
            raise SynthesisError(f"unknown voice {voice!r}; available: {known}")
        try:
            speed = float(speed)
        except (TypeError, ValueError) as exc:
            raise SynthesisError("speed must be a number") from exc
        if speed != speed or speed in {float("inf"), float("-inf")}:
            raise SynthesisError("speed must be a finite number")
        speed = min(4.0, max(0.25, speed))

        key = self._key(voice, speed, fmt, text, captioned)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        self._gate.acquire(self.settings.wait_timeout)
        try:
            cached = self._cache_get(key)
            if cached is not None:
                return cached
            started = time.perf_counter()
            chunks = split_for_synthesis(text)
            if not chunks:
                raise SynthesisError("input text is empty")
            parts: list[AudioData] = []
            for chunk in chunks:
                audio = self.engine.synthesize(chunk, voice, speed)
                if not audio.words:
                    audio.words = timings_from_duration(chunk, audio.duration)
                parts.append(audio)
            try:
                audio = parts[0] if len(parts) == 1 else concat(parts)
                payload, _ = encode(audio, fmt, self.settings.mp3_bitrate)
            except AudioError as exc:
                log.warning("audio encode failed: %s", exc)
                raise SynthesisError("could not encode audio in the requested format") from exc
            self._cache_put(key, payload, audio.words)
            log.info(
                "synthesized %d chars with %s/%s in %.2fs (%.1fs audio, %s)",
                len(text),
                self.engine.name,
                voice,
                time.perf_counter() - started,
                audio.duration,
                fmt,
            )
            return payload, audio.words
        finally:
            self._gate.release()

    # ---- cache ---------------------------------------------------------
    def _key(self, voice: str, speed: float, fmt: str, text: str, captioned: bool) -> str:
        raw = f"{self.engine.name}|{voice}|{speed:.3f}|{fmt}|{int(captioned)}|{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> tuple[bytes, tuple[WordTiming, ...]] | None:
        with self._cache_lock:
            value = self._cache.get(key)
            if value is None:
                return None
            self._cache.move_to_end(key)
            return value, self._cache_words.get(key, ())

    def _cache_put(
        self, key: str, value: bytes, words: tuple[WordTiming, ...] = ()
    ) -> None:
        limit = self.settings.cache_mb * 1024 * 1024
        if limit <= 0 or len(value) > limit:
            return
        with self._cache_lock:
            previous = self._cache.pop(key, None)
            if previous is not None:
                self._cache_bytes -= len(previous)
            self._cache_words.pop(key, None)
            self._cache[key] = value
            self._cache_words[key] = words
            self._cache_bytes += len(value)
            while self._cache_bytes > limit and self._cache:
                evicted_key, evicted = self._cache.popitem(last=False)
                self._cache_words.pop(evicted_key, None)
                self._cache_bytes -= len(evicted)
