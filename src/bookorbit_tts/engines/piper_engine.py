"""Piper engine (ONNX, ~60 MB per voice, real time on a Raspberry Pi)."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from ..audio import AudioData
from .base import Engine, Voice, guess_gender, humanize, language_name

log = logging.getLogger(__name__)


class PiperEngine(Engine):
    name = "piper"
    quality = 10

    def __init__(self, voices_dir: Path, default_voice: str | None = None) -> None:
        self.voices_dir = Path(voices_dir)
        self.default_voice = default_voice
        self._loaded: dict[str, object] = {}
        self._lock = threading.RLock()

    # ---- discovery -----------------------------------------------------
    def _pairs(self) -> dict[str, tuple[Path, Path]]:
        found: dict[str, tuple[Path, Path]] = {}
        if not self.voices_dir.is_dir():
            return found
        for model in sorted(self.voices_dir.glob("*.onnx")):
            config = model.with_suffix(".onnx.json")
            if config.exists():
                found[model.name[: -len(".onnx")]] = (model, config)
        return found

    def available(self) -> bool:
        return bool(self._pairs())

    def voices(self) -> list[Voice]:
        result = []
        for voice_id, (_, config_path) in self._pairs().items():
            result.append(self._voice_from_config(voice_id, config_path))
        return result

    def _voice_from_config(self, voice_id: str, config_path: Path) -> Voice:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            config = {}
        language = config.get("language") or {}
        code = language.get("code") or ""
        locale = code.replace("_", "-") or ""
        name = language.get("name_english") or language_name(code)
        if not name:
            espeak = (config.get("espeak") or {}).get("voice") or ""
            name = language_name(espeak)
        return Voice(
            id=voice_id,
            name=humanize(voice_id),
            short_name=voice_id,
            language=name,
            locale=locale,
            gender=guess_gender(voice_id),
        )

    # ---- synthesis -----------------------------------------------------
    def _pick(self, voice_id: str | None) -> str:
        pairs = self._pairs()
        if not pairs:
            raise RuntimeError(
                f"no Piper voices in {self.voices_dir}; run "
                "`bookorbit-tts download` or set BOOKORBIT_TTS_VOICE"
            )
        candidate = voice_id or self.default_voice
        if candidate and candidate in pairs:
            return candidate
        if not voice_id and pairs:
            return next(iter(pairs))
        raise KeyError(f"unknown Piper voice {candidate!r}")

    def _voice(self, voice_id: str):
        cached = self._loaded.get(voice_id)
        if cached is not None:
            return cached
        with self._lock:
            cached = self._loaded.get(voice_id)
            if cached is not None:
                return cached
            pairs = self._pairs()
            if voice_id not in pairs:
                raise KeyError(f"unknown Piper voice {voice_id!r}")
            from piper import PiperVoice

            model_path, config_path = pairs[voice_id]
            log.info("loading Piper voice %s", voice_id)
            voice = PiperVoice.load(str(model_path), config_path=str(config_path))
            # Two voices is plenty; more would just pin memory.
            if len(self._loaded) >= 2:
                self._loaded.pop(next(iter(self._loaded)))
            self._loaded[voice_id] = voice
            return voice

    def close(self) -> None:
        with self._lock:
            self._loaded.clear()

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        from piper.config import SynthesisConfig

        # One session run at a time. onnxruntime sessions are safe to share
        # across threads, but two runs on one core only fight each other.
        with self._lock:
            voice_id = self._pick(voice_id)
            voice = self._voice(voice_id)
            speed = min(4.0, max(0.25, speed))
            config = SynthesisConfig(length_scale=1.0 / speed, normalize_audio=True)
            pcm = b"".join(
                chunk.audio_int16_bytes for chunk in voice.synthesize(text, syn_config=config)
            )
            return AudioData(pcm=pcm, sample_rate=voice.config.sample_rate)
