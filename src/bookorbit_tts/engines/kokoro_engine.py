"""Kokoro-82M engine (more natural, ~6x real time on one modern core).

Kokoro is optional: it needs ``kokoro-onnx`` and a 140 MB model download.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from ..audio import AudioData, time_stretch
from .base import Engine, Voice, language_name

log = logging.getLogger(__name__)

# Kokoro voice ids start with a language letter and a gender letter.
_LANG = {
    "a": ("en-US", "en-us"),
    "b": ("en-GB", "en-gb"),
    "e": ("es-ES", "es"),
    "f": ("fr-FR", "fr-fr"),
    "h": ("hi-IN", "hi"),
    "i": ("it-IT", "it"),
    "j": ("ja-JP", "ja"),
    "p": ("pt-BR", "pt-br"),
    "z": ("zh-CN", "zh"),
}


class KokoroEngine(Engine):
    name = "kokoro"
    quality = 20

    def __init__(self, model_path: Path, voices_path: Path, default_voice: str | None = None) -> None:
        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)
        self.default_voice = default_voice or "af_heart"
        self._kokoro = None
        self._lock = threading.RLock()

    def available(self) -> bool:
        if not (self.model_path.is_file() and self.voices_path.is_file()):
            return False
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError:
            return False
        return True

    # ---- model ---------------------------------------------------------
    def _load(self):
        if self._kokoro is not None:
            return self._kokoro
        with self._lock:
            if self._kokoro is not None:
                return self._kokoro
            import numpy as np
            from kokoro_onnx import Kokoro

            log.info("loading Kokoro model %s", self.model_path.name)
            from ..logging_utils import silence_phonemizer

            silence_phonemizer()
            kokoro = Kokoro(str(self.model_path), str(self.voices_path))
            self._coerce_inputs(kokoro, np)
            self._kokoro = kokoro
            return kokoro

    @staticmethod
    def _coerce_inputs(kokoro, np) -> None:
        """kokoro-onnx sends int32 for a float32 ``speed`` input in some exports."""
        dtypes = {
            "tensor(float)": np.float32,
            "tensor(float16)": np.float16,
            "tensor(int64)": np.int64,
            "tensor(int32)": np.int32,
        }
        session = kokoro.sess
        original = session.run
        inputs = session.get_inputs()

        def run(output_names, input_feed, run_options=None):
            fixed = {}
            for spec in inputs:
                value = input_feed.get(spec.name)
                if value is None:
                    continue
                array = np.asarray(value)
                want = dtypes.get(spec.type)
                if want is not None and array.dtype != want:
                    array = array.astype(want)
                fixed[spec.name] = array
            return original(output_names, fixed, run_options)

        session.run = run

    # ---- voices --------------------------------------------------------
    def voices(self) -> list[Voice]:
        try:
            kokoro = self._load()
            ids = list(kokoro.voices.keys())
        except Exception as exc:  # model present but unusable
            log.warning("could not read Kokoro voices: %s", exc)
            return []
        result = []
        for voice_id in ids:
            lang = _LANG.get(voice_id[:1])
            locale = lang[0] if lang else ""
            language = language_name(locale) if locale else ""
            gender = {"f": "Female", "m": "Male"}.get(voice_id[1:2], "Unknown")
            name = voice_id[3:].replace("_", " ").strip().title() or voice_id
            result.append(
                Voice(
                    id=voice_id,
                    name=name,
                    short_name=voice_id,
                    language=language,
                    locale=locale,
                    gender=gender,
                )
            )
        return result

    # ---- synthesis -----------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self._kokoro = None

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        import numpy as np

        with self._lock:
            kokoro = self._load()
            voice_id = voice_id or self.default_voice
            if voice_id not in kokoro.voices:
                raise KeyError(f"unknown Kokoro voice {voice_id!r}")

            requested = min(4.0, max(0.25, speed))
            lang = _LANG.get(voice_id[:1], ("en-US", "en-us"))[1]

            # The int8 export truncates its `speed` input to an integer (and fails
            # below 1.0), so render at 1.0 and time-stretch afterwards instead.
            audio, sample_rate = kokoro.create(
                text, voice=voice_id, speed=1.0, lang=lang, trim=True
            )
            audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
            pcm = (audio * 32767.0).astype(np.int16).tobytes()
            rendered = AudioData(pcm=pcm, sample_rate=sample_rate)
            return time_stretch(rendered, requested)
