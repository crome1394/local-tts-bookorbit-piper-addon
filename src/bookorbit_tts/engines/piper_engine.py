"""Piper engine (ONNX, one voice resident, real time on a small CPU)."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterable
from pathlib import Path

from ..audio import AudioData
from ..config import PIPER_VOICE_ID
from ..timings import timings_from_alignments
from .base import Engine, Voice, guess_gender, humanize, language_name

log = logging.getLogger(__name__)

# A 4 GB container does not need a shelf of high-quality models resident
# on disk listings. Two are loaded at a time; this caps how many we even index.
_MAX_VOICES = 64


class PiperEngine(Engine):
    name = "piper"
    quality = 10

    def __init__(
        self,
        voices_dir: Path | Iterable[Path],
        default_voice: str | None = None,
    ) -> None:
        if isinstance(voices_dir, Path):
            self.voices_dirs = [voices_dir]
        else:
            self.voices_dirs = [Path(directory) for directory in voices_dir]
        self.voices_dir = self.voices_dirs[0] if self.voices_dirs else Path(".")
        self.default_voice = default_voice
        self._loaded: dict[str, object] = {}
        self._lock = threading.RLock()

    # ---- discovery -----------------------------------------------------
    def _pairs(self) -> dict[str, tuple[Path, Path]]:
        """Find ``name.onnx`` + ``name.onnx.json`` under each voices directory.

        A Hugging Face checkout of rhasspy/piper-voices is nested
        (``en/en_US/ryan/high/en_US-ryan-high.onnx``). Flat files in the same
        directory work too. The filename has to be a Piper voice id, and both
        files have to stay inside the directory they were found in.
        """
        found: dict[str, tuple[Path, Path]] = {}
        for root in self.voices_dirs:
            if not root.is_dir():
                continue
            try:
                root_real = root.resolve()
            except OSError:
                continue
            for model in sorted(root.rglob("*.onnx")):
                if len(found) >= _MAX_VOICES:
                    log.warning("stopped at %d Piper voices under %s", _MAX_VOICES, root)
                    return found
                voice_id = model.name[: -len(".onnx")]
                if voice_id in found or not PIPER_VOICE_ID.fullmatch(voice_id):
                    continue
                config = Path(f"{model}.json")
                if not config.is_file():
                    continue
                if not _inside(root_real, model) or not _inside(root_real, config):
                    log.warning("skipping %s; it resolves outside %s", model, root)
                    continue
                found[voice_id] = (model, config)
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
            where = ", ".join(str(directory) for directory in self.voices_dirs) or "(none)"
            raise RuntimeError(
                f"no Piper voices in {where}; drop a voice into the voices "
                "directory or run `bookorbit-tts download`"
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
            # Alignments expose phoneme lengths the model already computed.
            # Without the onnx package, Piper loads the file unchanged.
            voice = PiperVoice.load(
                str(model_path),
                config_path=str(config_path),
                include_alignments=True,
            )
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
            pieces: list[bytes] = []
            alignments: list[tuple[str, int]] = []
            sample_rate = voice.config.sample_rate
            for chunk in voice.synthesize(text, syn_config=config, include_alignments=True):
                pieces.append(chunk.audio_int16_bytes)
                sample_rate = chunk.sample_rate
                for alignment in chunk.phoneme_alignments or []:
                    alignments.append((alignment.phoneme, int(alignment.num_samples)))
            audio = AudioData(pcm=b"".join(pieces), sample_rate=sample_rate)
            if alignments:
                audio.words = timings_from_alignments(text, alignments, sample_rate)
            return audio


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True
