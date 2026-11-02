import io
import wave

import pytest

from bookorbit_tts.audio import AudioData, concat, encode, time_stretch, to_wav


def tone(seconds: float = 1.0, rate: int = 22050) -> AudioData:
    frames = int(seconds * rate)
    # A quiet square wave; content does not matter, only the byte layout.
    pcm = b"".join((b"\x00\x10" if (i // 40) % 2 else b"\x00\xf0") for i in range(frames))
    return AudioData(pcm=pcm, sample_rate=rate)


def test_wav_roundtrip():
    audio = tone()
    payload = to_wav(audio)
    with wave.open(io.BytesIO(payload), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == audio.sample_rate
        assert wav.getnframes() == len(audio.pcm) // 2


def test_mp3_starts_with_a_frame_or_id3():
    payload, content_type = encode(tone(), "mp3")
    assert content_type == "audio/mpeg"
    assert payload[:3] == b"ID3" or payload[0] == 0xFF


def test_unknown_format_is_rejected():
    with pytest.raises(Exception):
        encode(tone(), "ogg-vorbis")


def test_concat_inserts_silence():
    one = tone(0.1)
    joined = concat([one, one], gap_ms=100)
    assert len(joined.pcm) == len(one.pcm) * 2 + int(0.1 * one.sample_rate) * 2


def test_time_stretch_changes_duration():
    audio = tone(2.0)
    faster = time_stretch(audio, 2.0)
    slower = time_stretch(audio, 0.5)
    assert faster.duration < audio.duration < slower.duration
