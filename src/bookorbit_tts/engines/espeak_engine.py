"""espeak-ng fallback: robotic, but tiny and instant on any hardware."""

from __future__ import annotations

import io
import shutil
import subprocess
import wave

from ..audio import AudioData
from .base import Engine, Voice, language_name

_BASE_WPM = 175


class EspeakEngine(Engine):
    name = "espeak"
    quality = 0

    def __init__(self, default_voice: str | None = None) -> None:
        self.default_voice = default_voice or "en-us"
        self._voices: list[Voice] | None = None

    def _binary(self) -> str | None:
        return shutil.which("espeak-ng") or shutil.which("espeak")

    def available(self) -> bool:
        return self._binary() is not None

    def voices(self) -> list[Voice]:
        if self._voices is not None:
            return self._voices
        binary = self._binary()
        if not binary:
            return []
        try:
            output = subprocess.run(
                [binary, "--voices"], capture_output=True, text=True, check=True, timeout=10
            ).stdout
        except (subprocess.SubprocessError, OSError):
            return []
        voices: list[Voice] = []
        for line in output.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4:
                continue
            lang, gender = fields[1], fields[2]
            name = fields[3].capitalize()
            voices.append(
                Voice(
                    id=lang,
                    name=name,
                    short_name=lang,
                    language=language_name(lang),
                    locale=_locale(lang),
                    gender={"M": "Male", "F": "Female"}.get(gender.upper(), "Unknown"),
                )
            )
        self._voices = voices
        return voices

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        binary = self._binary()
        if not binary:
            raise RuntimeError("espeak-ng is not installed")
        wpm = int(min(450, max(80, _BASE_WPM * min(4.0, max(0.25, speed)))))
        voice = voice_id or self.default_voice
        if (
            not voice
            or voice.startswith("-")
            or any(character.isspace() for character in voice)
            or len(voice) > 64
        ):
            raise RuntimeError("invalid espeak voice id")
        # "--" keeps a sentence that starts with a dash from being read as a flag.
        # espeak-ng treats -f as "read this file" and -w as "write a wav".
        command = [
            binary,
            "-v",
            voice,
            "-s",
            str(wpm),
            "--stdout",
            "--",
            text,
        ]
        result = subprocess.run(command, capture_output=True, check=False, timeout=60)
        if result.returncode != 0 or not result.stdout:
            detail = result.stderr.decode("utf-8", "replace").strip()[:200]
            raise RuntimeError(f"espeak-ng failed: {detail}")
        with wave.open(io.BytesIO(result.stdout), "rb") as wav:
            pcm = wav.readframes(wav.getnframes())
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
        if channels > 1 or width != 2:
            pcm, sample_rate = _to_mono16(pcm, channels, width, sample_rate)
        return AudioData(pcm=pcm, sample_rate=sample_rate)


def _locale(code: str) -> str:
    parts = code.replace("_", "-").split("-")
    if len(parts) == 1:
        return parts[0].lower()
    return f"{parts[0].lower()}-{parts[1].upper()}"


def _to_mono16(pcm: bytes, channels: int, width: int, rate: int) -> tuple[bytes, int]:
    import array

    samples = array.array("h")
    samples.frombytes(pcm)
    if width != 2:
        raise RuntimeError("unexpected espeak sample width")
    if channels > 1:
        samples = array.array("h", samples[::channels])
    return samples.tobytes(), rate
