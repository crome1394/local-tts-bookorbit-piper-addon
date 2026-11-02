"""Engine interface shared by Piper, Kokoro and espeak-ng."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from ..audio import AudioData

LANGUAGE_NAMES = {
    "ar": "Arabic",
    "az": "Azerbaijani",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ka": "Georgian",
    "kk": "Kazakh",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh": "Chinese",
}

_MALE_HINTS = {
    "adam", "alan", "alex", "andrew", "brian", "daniel", "david", "george",
    "guy", "joe", "john", "michael", "paul", "ryan", "thomas", "tony", "william",
}
_FEMALE_HINTS = {
    "alba", "alloy", "aoede", "bella", "emma", "female", "hannah", "heart",
    "jessica", "kore", "lessac", "lily", "nicole", "nova", "river", "sarah",
    "sky", "sophie", "woman",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.split("-")[0].split("_")[0].lower(), "")


def guess_gender(voice_id: str) -> str:
    words = set(re.split(r"[_\-\s]+", voice_id.lower()))
    if words & _FEMALE_HINTS:
        return "Female"
    if words & _MALE_HINTS:
        return "Male"
    return "Unknown"


def humanize(voice_id: str) -> str:
    """``en_US-hfc_female-medium`` -> ``HFC Female``."""
    tail = voice_id
    if "-" in tail:
        parts = tail.split("-")
        # Drop the leading locale and the trailing quality marker.
        if len(parts) >= 3:
            tail = "-".join(parts[1:-1])
        else:
            tail = parts[-1]
    return " ".join(word.capitalize() for word in re.split(r"[_\-]+", tail) if word) or voice_id


@dataclass
class Voice:
    id: str
    name: str
    short_name: str
    language: str
    locale: str
    gender: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["voice_id"] = payload["id"]
        payload["display_name"] = payload["name"]
        return payload


class Engine(ABC):
    name: str = "base"
    quality: int = 0  # higher wins when several engines are usable

    @abstractmethod
    def available(self) -> bool:
        """Whether the engine's dependencies and voices are present."""

    @abstractmethod
    def voices(self) -> list[Voice]:
        """Installed voices."""

    @abstractmethod
    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        """Render one chunk of text. Must be safe to call from any thread."""

    def close(self) -> None:  # pragma: no cover - optional cleanup
        pass
