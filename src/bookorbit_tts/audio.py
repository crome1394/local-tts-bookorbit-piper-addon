"""Audio encoding: 16-bit mono PCM in, container bytes out.

WAV and raw PCM are produced in-process. MP3 uses ``lameenc`` when it is
installed, otherwise ffmpeg. Everything else (flac/opus/aac) is delegated to
ffmpeg, because shipping those encoders in-process is not worth the ~100 MB.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import wave
from dataclasses import dataclass, field

from .timings import WordTiming

SAMPLE_WIDTH = 2  # int16

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "pcm": "audio/L16",
    "flac": "audio/flac",
    "opus": "audio/ogg",
    "aac": "audio/aac",
}

SUPPORTED = tuple(CONTENT_TYPES)


class AudioError(RuntimeError):
    """Raised when a requested format cannot be produced."""


@dataclass
class AudioData:
    pcm: bytes  # little-endian signed 16-bit mono
    sample_rate: int
    words: tuple[WordTiming, ...] = field(default_factory=tuple)

    @property
    def duration(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return len(self.pcm) / (SAMPLE_WIDTH * self.sample_rate)


def to_wav(audio: AudioData) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(audio.sample_rate)
        wav.writeframes(audio.pcm)
    return buffer.getvalue()


def concat(parts: list[AudioData], gap_ms: int = 120) -> AudioData:
    """Join clips, inserting a short pause so sentences do not run together."""
    if not parts:
        return AudioData(b"", 24000)
    rate = parts[0].sample_rate
    if any(part.sample_rate != rate for part in parts):
        raise AudioError("cannot join audio chunks that use different sample rates")
    silence = b"\x00\x00" * int(rate * gap_ms / 1000)
    gap_s = gap_ms / 1000
    chunks: list[bytes] = []
    words: list[WordTiming] = []
    offset = 0.0
    for index, part in enumerate(parts):
        if index:
            chunks.append(silence)
            offset += gap_s
        chunks.append(part.pcm)
        words.extend(
            WordTiming(word.word, word.start + offset, word.end + offset) for word in part.words
        )
        offset += part.duration
    return AudioData(b"".join(chunks), rate, tuple(words))


def encode(audio: AudioData, fmt: str, mp3_bitrate: int = 64) -> tuple[bytes, str]:
    """Return ``(bytes, content_type)`` for the requested format."""
    fmt = (fmt or "mp3").lower()
    if fmt == "wav":
        return to_wav(audio), CONTENT_TYPES["wav"]
    if fmt == "pcm":
        return audio.pcm, CONTENT_TYPES["pcm"]
    if fmt == "mp3":
        return _mp3(audio, mp3_bitrate), CONTENT_TYPES["mp3"]
    if fmt in {"flac", "opus", "aac"}:
        return _ffmpeg(audio, fmt), CONTENT_TYPES[fmt]
    raise AudioError(f"unsupported response_format {fmt!r}")


def time_stretch(audio: AudioData, factor: float) -> AudioData:
    """Change duration by ``factor`` (2.0 = twice as fast).

    Uses ffmpeg's ``atempo`` when available so the pitch is preserved; falls
    back to resampling, which shifts pitch, on minimal installs.
    """
    if abs(factor - 1.0) < 0.01 or not audio.pcm:
        return audio
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            return _atempo(audio, factor, ffmpeg)
        except AudioError:
            pass
    return _resample(audio, factor)


def _atempo(audio: AudioData, factor: float, ffmpeg: str) -> AudioData:
    remaining = factor
    filters: list[str] = []
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-filter:a",
        ",".join(filters),
        "-f",
        "wav",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, input=to_wav(audio), capture_output=True, check=False, timeout=60
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioError("ffmpeg atempo timed out") from exc
    if result.returncode != 0 or not result.stdout:
        raise AudioError("ffmpeg atempo failed")
    with wave.open(io.BytesIO(result.stdout), "rb") as wav:
        return AudioData(wav.readframes(wav.getnframes()), wav.getframerate())


def _resample(audio: AudioData, factor: float) -> AudioData:
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy ships with the engines
        return audio
    samples = np.frombuffer(audio.pcm, dtype=np.int16).astype(np.float32)
    if samples.size < 2:
        return audio
    target = max(1, int(round(samples.size / factor)))
    source_axis = np.arange(samples.size, dtype=np.float64)
    target_axis = np.linspace(0.0, samples.size - 1, num=target, dtype=np.float64)
    stretched = np.interp(target_axis, source_axis, samples).astype(np.int16)
    return AudioData(stretched.tobytes(), audio.sample_rate)


def _mp3(audio: AudioData, bitrate: int) -> bytes:
    try:
        import lameenc
    except ImportError:
        return _ffmpeg(audio, "mp3", bitrate)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(audio.sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(5)
    return bytes(encoder.encode(audio.pcm) + encoder.flush())


def _ffmpeg(audio: AudioData, fmt: str, bitrate: int = 64) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError(
            f"{fmt} output needs ffmpeg (not installed); use wav or mp3 instead"
        )
    if fmt == "mp3":
        args = ["-f", "mp3", "-b:a", f"{bitrate}k"]
    elif fmt == "flac":
        args = ["-f", "flac"]
    elif fmt == "opus":
        args = ["-c:a", "libopus", "-b:a", "48k", "-f", "ogg"]
    elif fmt == "aac":
        args = ["-c:a", "aac", "-b:a", f"{bitrate}k", "-f", "adts"]
    else:  # pragma: no cover - guarded by encode()
        raise AudioError(f"unsupported format {fmt}")

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(audio.sample_rate),
        "-ac",
        "1",
        "-i",
        "pipe:0",
        *args,
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, input=audio.pcm, capture_output=True, check=False, timeout=60
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f"ffmpeg timed out while encoding {fmt}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()[:300]
        raise AudioError(f"ffmpeg failed to encode {fmt}: {detail}")
    return result.stdout
