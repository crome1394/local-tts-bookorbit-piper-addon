"""Configuration for the BookOrbit TTS server.

Everything is set through ``BOOKORBIT_TTS_*`` environment variables so the
server can be started from systemd or Docker without a config file.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "BOOKORBIT_TTS_"

# CC0 voice, safe to redistribute with the public portable bundle.
DEFAULT_PIPER_VOICE = "en_US-joe-medium"
DEFAULT_KOKORO_VOICE = "af_heart"

# Piper ids look like en_US-joe-medium. The quality group is a fixed set so a
# value cannot smuggle a slash into a download path.
PIPER_VOICE_ID = re.compile(
    r"^[a-z]{2,3}_[A-Za-z]{2,8}-[A-Za-z0-9_]{1,48}-(?:x_low|low|medium|high)$"
)
# Ids accepted from clients: Piper, Kokoro (af_heart), and espeak (en-us+f3).
VOICE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+:.-]{0,79}")
_HOST_RE = re.compile(r"[A-Za-z0-9:.][A-Za-z0-9.:_-]{0,252}")
_LOG_LEVELS = {"debug", "info", "warning", "error"}
_ENGINES = {"auto", "piper", "kokoro", "espeak"}

KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.1/kokoro-v1.0.int8.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.1/voices-v1.0.bin"
)
# The int8 model is about 88 MB and the voice bank about 28 MB. The caps sit
# well above that and stop a redirected response from filling the disk.
KOKORO_MODEL_MAX_BYTES = 200 * 1024 * 1024
KOKORO_VOICES_MAX_BYTES = 64 * 1024 * 1024

# Hard ceilings for a 2-core / 4 GB container. Past these, ONNX or the audio
# buffer crowds out BookOrbit.
MAX_THREADS = 8
MAX_CONCURRENCY = 4
MAX_QUEUE = 16
MAX_CACHE_MB = 256
MAX_TEXT_CHARS = 20_000
MAX_WAIT_S = 120.0


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(ENV_PREFIX + name, default)


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{ENV_PREFIX}{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{ENV_PREFIX}{name} must be a number, got {raw!r}") from exc


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "bookorbit-tts"


def _check_host(host: str) -> str:
    host = host.strip()
    if not _HOST_RE.fullmatch(host):
        raise ValueError(
            f"invalid host {host!r}; use an address such as 127.0.0.1 or 0.0.0.0"
        )
    return host


def _check_api_key(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 256 or any(character.isspace() for character in value):
        raise ValueError(f"{ENV_PREFIX}API_KEY must be one token of at most 256 characters")
    return value


def _between(name: str, value: float, low: float, high: float) -> None:
    if not math.isfinite(value) or value < low or value > high:
        raise ValueError(f"{ENV_PREFIX}{name} must be from {low:g} to {high:g}")


@dataclass
class Settings:
    """Runtime settings.

    ``engine`` is one of ``auto``, ``piper``, ``kokoro`` or ``espeak``.
    ``auto`` benchmarks the installed engines on startup and keeps the most
    natural one that can still synthesize faster than real time.
    """

    host: str = "127.0.0.1"
    port: int = 8765
    engine: str = "auto"
    default_voice: str | None = None
    data_dir: Path = field(default_factory=_default_data_dir)
    threads: int = 1
    concurrency: int = 1
    queue: int = 4
    wait_timeout: float = 60.0
    auto_min_rtf: float = 1.5
    api_key: str | None = None
    cache_mb: int = 32
    mp3_bitrate: int = 64
    max_text_chars: int = 4000
    log_level: str = "info"
    docs: bool = False

    def __post_init__(self) -> None:
        self.host = _check_host(self.host)
        _between("PORT", self.port, 1, 65535)
        self.port = int(self.port)
        self.engine = self.engine.lower()
        if self.engine not in _ENGINES:
            raise ValueError(f"unknown engine {self.engine!r}")
        if self.default_voice is not None and not VOICE_ID.fullmatch(self.default_voice):
            raise ValueError(f"invalid voice id {self.default_voice!r}")
        data_dir = str(self.data_dir)
        if "\n" in data_dir or "\x00" in data_dir:
            raise ValueError("data directory must be a single path")
        _between("THREADS", self.threads, 0, MAX_THREADS)
        self.threads = int(self.threads)
        _between("CONCURRENCY", self.concurrency, 1, MAX_CONCURRENCY)
        self.concurrency = int(self.concurrency)
        _between("QUEUE", self.queue, 0, MAX_QUEUE)
        self.queue = int(self.queue)
        _between("WAIT_TIMEOUT", self.wait_timeout, 1, MAX_WAIT_S)
        _between("AUTO_MIN_RTF", self.auto_min_rtf, 0.1, 100)
        _between("CACHE_MB", self.cache_mb, 0, MAX_CACHE_MB)
        self.cache_mb = int(self.cache_mb)
        _between("MP3_BITRATE", self.mp3_bitrate, 16, 320)
        self.mp3_bitrate = int(self.mp3_bitrate)
        _between("MAX_TEXT_CHARS", self.max_text_chars, 1, MAX_TEXT_CHARS)
        self.max_text_chars = int(self.max_text_chars)
        self.api_key = _check_api_key(self.api_key)
        self.log_level = self.log_level.lower()
        if self.log_level == "warn":
            self.log_level = "warning"
        if self.log_level not in _LOG_LEVELS:
            raise ValueError(f"invalid log level {self.log_level!r}")

    # ---- derived paths -------------------------------------------------
    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    def voice_dirs(self) -> list[Path]:
        """Directories scanned for Piper voices.

        ``BOOKORBIT_TTS_VOICES_DIR`` is the drop folder (a Hugging Face
        checkout can sit here as-is). ``data/voices`` is always included
        and is where ``bookorbit-tts download`` writes.
        """
        directories: list[Path] = []
        extra = _env("VOICES_DIR")
        if extra:
            directories.append(Path(extra).expanduser())
        directories.append(self.voices_dir)
        unique: list[Path] = []
        seen: set[str] = set()
        for directory in directories:
            key = str(directory)
            if key in seen:
                continue
            seen.add(key)
            unique.append(directory)
        return unique

    @property
    def kokoro_dir(self) -> Path:
        return self.data_dir / "kokoro"

    @property
    def kokoro_model(self) -> Path:
        return Path(_env("KOKORO_MODEL", str(self.kokoro_dir / "kokoro-v1.0.int8.onnx")))

    @property
    def kokoro_voices(self) -> Path:
        return Path(_env("KOKORO_VOICES", str(self.kokoro_dir / "voices-v1.0.bin")))

    def ensure_dirs(self) -> None:
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.kokoro_dir.mkdir(parents=True, exist_ok=True)

    def exposed_without_key(self) -> bool:
        """True when the bind address is reachable beyond this machine and no key is set."""
        if self.api_key:
            return False
        return self.host.lower() not in {"127.0.0.1", "localhost", "::1"}

    def body_limit_bytes(self) -> int:
        """Upper bound for one HTTP body. Generous for JSON, small enough to cap RAM."""
        return min(1_048_576, max(65_536, self.max_text_chars * 8 + 4096))

    # ---- construction --------------------------------------------------
    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(_env("DATA_DIR") or _default_data_dir()).expanduser()
        return cls(
            host=_env("HOST", "127.0.0.1") or "127.0.0.1",
            port=_env_int("PORT", 8765),
            engine=(_env("ENGINE", "auto") or "auto").lower(),
            default_voice=_env("VOICE") or None,
            data_dir=data_dir,
            threads=_env_int("THREADS", 1),
            concurrency=_env_int("CONCURRENCY", 1),
            queue=_env_int("QUEUE", 4),
            wait_timeout=_env_float("WAIT_TIMEOUT", 60.0),
            auto_min_rtf=_env_float("AUTO_MIN_RTF", 1.5),
            api_key=_env("API_KEY") or None,
            cache_mb=_env_int("CACHE_MB", 32),
            mp3_bitrate=_env_int("MP3_BITRATE", 64),
            max_text_chars=_env_int("MAX_TEXT_CHARS", 4000),
            log_level=(_env("LOG_LEVEL", "info") or "info").lower(),
            docs=_env_bool("DOCS", False),
        )

    def resolved_engine(self, available: str) -> str:
        """Return the effective engine name, applying the default voice."""
        return available if self.engine == "auto" else self.engine

    def voice_for(self, engine: str) -> str:
        if self.default_voice:
            return self.default_voice
        return DEFAULT_KOKORO_VOICE if engine == "kokoro" else DEFAULT_PIPER_VOICE
