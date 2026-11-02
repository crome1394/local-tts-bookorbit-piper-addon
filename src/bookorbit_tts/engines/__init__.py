"""Engine construction and startup benchmarking."""

from __future__ import annotations

import gc
import logging
import os
import socket
import time
import urllib.request
from pathlib import Path

from ..audio import AudioData
from ..config import (
    KOKORO_MODEL_MAX_BYTES,
    KOKORO_MODEL_URL,
    KOKORO_VOICES_MAX_BYTES,
    KOKORO_VOICES_URL,
    PIPER_VOICE_ID,
    Settings,
)
from .base import Engine
from .espeak_engine import EspeakEngine
from .kokoro_engine import KokoroEngine
from .piper_engine import PiperEngine

log = logging.getLogger(__name__)

BENCH_TEXT = (
    "This is a short benchmark passage, read aloud at a normal pace, "
    "to measure how much faster than real time this machine can speak."
)


def make_engines(settings: Settings) -> dict[str, Engine]:
    engines: dict[str, Engine] = {}
    kokoro = KokoroEngine(settings.kokoro_model, settings.kokoro_voices, settings.default_voice)
    if kokoro.available():
        engines["kokoro"] = kokoro
    piper = PiperEngine(settings.voices_dir, settings.default_voice)
    if piper.available():
        engines["piper"] = piper
    espeak = EspeakEngine(settings.default_voice)
    if espeak.available():
        engines["espeak"] = espeak
    return engines


def benchmark(engine: Engine, text: str = BENCH_TEXT, voice_id: str | None = None) -> float:
    """Return the real-time factor (audio seconds per wall second)."""
    voices = engine.voices()
    if not voices:
        return 0.0
    known = {voice.id for voice in voices}
    voice = voice_id if voice_id in known else voices[0].id
    started = time.perf_counter()
    try:
        audio = engine.synthesize(text, voice, 1.0)
        # A second run removes one-time model loading from the measurement.
        started = time.perf_counter()
        audio = engine.synthesize(text, voice, 1.0)
    except Exception as exc:  # noqa: BLE001 - a broken engine simply loses
        log.warning("%s benchmark failed: %s", engine.name, exc)
        return 0.0
    elapsed = max(1e-6, time.perf_counter() - started)
    return audio.duration / elapsed


def select_engine(settings: Settings) -> tuple[Engine, dict[str, float]]:
    engines = make_engines(settings)
    if not engines:
        raise RuntimeError(
            "no TTS engine is usable. Run `bookorbit-tts doctor` for details, "
            "or install a Piper voice with `bookorbit-tts download`."
        )

    scores: dict[str, float] = {}

    if settings.engine != "auto":
        engine = engines.get(settings.engine)
        if engine is None:
            raise RuntimeError(
                f"engine {settings.engine!r} is not available; installed: "
                + ", ".join(sorted(engines))
            )
        for other in engines.values():
            if other is not engine:
                other.close()
        return engine, scores

    # Kokoro needs roughly two threads to stay ahead of playback. Loading it
    # just to reject it costs time and several hundred MB, which matters on the
    # small machines this server targets. One thread therefore means Piper.
    if settings.threads == 1 and "kokoro" in engines and len(engines) > 1:
        log.info(
            "skipping the Kokoro benchmark with THREADS=1; "
            "use THREADS=2 or --engine kokoro to try it"
        )
        engines.pop("kokoro").close()

    if not engines:  # pragma: no cover - espeak is always a candidate
        raise RuntimeError("no TTS engine is usable at THREADS=1")

    # Highest quality first. Stop at the first engine that is comfortably
    # faster than real time so a rejected Kokoro model is not joined by a
    # Piper model that we then have to unload, and so a winner does not make
    # us load every slower engine too.
    chosen: Engine | None = None
    best: Engine | None = None
    best_score = -1.0
    for name in sorted(engines, key=lambda key: engines[key].quality, reverse=True):
        engine = engines[name]
        score = benchmark(engine, voice_id=settings.default_voice)
        scores[name] = round(score, 1)
        if score >= settings.auto_min_rtf:
            log.info(
                "auto-selected %s (%.1fx real time; threshold %.1fx)",
                name,
                score,
                settings.auto_min_rtf,
            )
            chosen = engine
            break
        log.info("%s too slow for smooth playback (%.1fx real time)", name, score)
        if score > best_score:
            if best is not None:
                best.close()
            best = engine
            best_score = score
        else:
            engine.close()

    if chosen is None:
        chosen = best
        if chosen is None:  # pragma: no cover - engines was non-empty
            raise RuntimeError("no TTS engine is usable")
        log.warning(
            "no engine reached %.1fx real time; using %s at %.1fx",
            settings.auto_min_rtf,
            chosen.name,
            scores.get(chosen.name, 0.0),
        )
    for other in engines.values():
        if other is not chosen:
            other.close()
    gc.collect()
    return chosen, scores


def download_piper_voices(voices: list[str], voices_dir: Path) -> list[str]:
    from piper.download_voices import download_voice

    voices_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for voice in voices:
        voice = voice.strip()
        if not PIPER_VOICE_ID.fullmatch(voice):
            log.error("refusing voice id %r; expected a name like en_US-joe-medium", voice)
            continue
        started = time.time()
        previous_timeout = socket.getdefaulttimeout()
        try:
            # piper.download_voices uses urlopen with no timeout of its own.
            socket.setdefaulttimeout(120)
            download_voice(voice, voices_dir)
            done.append(voice)
        except Exception as exc:  # noqa: BLE001
            log.error("could not download %s: %s", voice, exc)
            for suffix in (".onnx", ".onnx.json"):
                partial = voices_dir / f"{voice}{suffix}"
                if partial.is_file() and partial.stat().st_mtime >= started - 1:
                    partial.unlink(missing_ok=True)
        finally:
            socket.setdefaulttimeout(previous_timeout)
    return done


def download_kokoro(settings: Settings) -> None:
    settings.kokoro_dir.mkdir(parents=True, exist_ok=True)
    _download_limited(KOKORO_MODEL_URL, settings.kokoro_model, KOKORO_MODEL_MAX_BYTES)
    _download_limited(KOKORO_VOICES_URL, settings.kokoro_voices, KOKORO_VOICES_MAX_BYTES)


def _download_limited(url: str, target: Path, max_bytes: int) -> None:
    """Download ``url`` to ``target`` without writing a partial file in place."""
    if not url.startswith("https://"):
        raise RuntimeError(f"refusing non-HTTPS download {url}")
    if target.is_file() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "bookorbit-tts"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as handle:
            final = response.geturl()
            if not final.startswith("https://"):
                raise RuntimeError("download redirected off HTTPS")
            total = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"download exceeded {max_bytes} bytes")
                handle.write(chunk)
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError(f"empty download from {url}")
        os.replace(partial, target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def silence(seconds: float, sample_rate: int = 24000) -> AudioData:
    return AudioData(b"\x00\x00" * int(seconds * sample_rate), sample_rate)
