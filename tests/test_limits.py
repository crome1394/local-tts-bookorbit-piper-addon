import io
import shutil
import subprocess
import threading
import wave

import pytest

from bookorbit_tts.audio import AudioData, _ffmpeg
from bookorbit_tts.config import Settings
from bookorbit_tts.engines import download_piper_voices
from bookorbit_tts.engines.base import Engine, Voice
from bookorbit_tts.engines.espeak_engine import EspeakEngine
from bookorbit_tts.synthesizer import ServerBusy, Synthesizer


def _voice() -> Voice:
    return Voice(
        id="en_US-joe-medium",
        name="Joe",
        short_name="Joe",
        language="English",
        locale="en-US",
        gender="Male",
    )


class _Fake(Engine):
    name = "piper"
    quality = 1

    def __init__(self, pcm: bytes = b"\x00\x01" * 1000) -> None:
        self._pcm = pcm
        self.calls = 0

    def available(self) -> bool:
        return True

    def voices(self) -> list[Voice]:
        return [_voice()]

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        self.calls += 1
        return AudioData(pcm=self._pcm, sample_rate=16000)


class _Holding(_Fake):
    def __init__(self) -> None:
        super().__init__(pcm=b"\x00\x00" * 200)
        self.started = threading.Event()
        self.release = threading.Event()

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioData:
        self.started.set()
        assert self.release.wait(2)
        return super().synthesize(text, voice_id, speed)


def test_replaced_cache_entry_is_not_counted_twice(tmp_path):
    synth = Synthesizer(_Fake(), Settings(engine="piper", data_dir=tmp_path, cache_mb=1))
    synth._cache_put("same", b"abc")
    synth._cache_put("same", b"wxyz")
    assert synth._cache_bytes == 4
    assert list(synth._cache.values()) == [b"wxyz"]


def test_captioned_requests_reuse_one_synthesis(tmp_path):
    engine = _Fake()
    synth = Synthesizer(engine, Settings(engine="piper", data_dir=tmp_path))
    first, words = synth.speak_captioned("Hello there", None, 1.0, "wav")
    second, again = synth.speak_captioned("Hello there", None, 1.0, "wav")
    assert engine.calls == 1
    assert first == second
    assert [word.word for word in words] == ["Hello", "there"]
    assert again == words


def test_cache_stays_inside_its_budget(tmp_path):
    pcm = b"\x00\x01" * 200_000
    synth = Synthesizer(_Fake(pcm), Settings(engine="piper", data_dir=tmp_path, cache_mb=1))
    for index in range(4):
        synth.speak(f"sentence {index}", None, 1.0, "wav")
    assert synth._cache_bytes <= 1024 * 1024
    assert synth._cache


def test_a_full_queue_rejects_the_extra_request(tmp_path):
    engine = _Holding()
    synth = Synthesizer(
        engine,
        Settings(engine="piper", data_dir=tmp_path, concurrency=1, queue=0, wait_timeout=2),
    )
    errors: list[BaseException] = []

    def run() -> None:
        try:
            synth.speak("Please wait.", None, 1.0, "wav")
        except BaseException as exc:  # noqa: BLE001 - the test records it
            errors.append(exc)

    first = threading.Thread(target=run)
    first.start()
    assert engine.started.wait(2)
    with pytest.raises(ServerBusy):
        synth.speak("Please wait.", None, 1.0, "wav")
    engine.release.set()
    first.join(2)
    assert errors == []


def test_settings_reject_a_host_that_could_rewrite_a_unit_file():
    with pytest.raises(ValueError):
        Settings(host='127.0.0.1"\nExecStart=/bin/sh')


def test_settings_reject_too_many_threads():
    with pytest.raises(ValueError):
        Settings(threads=32)


def test_download_refuses_a_path_like_voice_id(tmp_path, monkeypatch):
    called: list[str] = []

    def fake_download(voice, directory, force_redownload=False):
        called.append(voice)

    monkeypatch.setattr("piper.download_voices.download_voice", fake_download)
    done = download_piper_voices(["../etc/passwd", "en_US-joe-medium/../../escape"], tmp_path)
    assert done == []
    assert called == []


def test_espeak_text_cannot_become_a_flag(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b"\x00\x00" * 220)
        completed = subprocess.CompletedProcess(command, 0, stdout=buffer.getvalue(), stderr=b"")
        return completed

    monkeypatch.setattr("bookorbit_tts.engines.espeak_engine.subprocess.run", fake_run)
    engine = EspeakEngine()
    monkeypatch.setattr(engine, "_binary", lambda: "espeak-ng")
    engine.synthesize("-w /tmp/stolen.wav", "en-us", 1.0)
    command = captured["command"]
    assert command[command.index("--") + 1] == "-w /tmp/stolen.wav"
    assert "-w" not in command[: command.index("--")]


def test_ffmpeg_encode_has_a_timeout(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=b"ID3", stderr=b"")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr("bookorbit_tts.audio.subprocess.run", fake_run)
    _ffmpeg(AudioData(b"\x00\x00" * 20, 16000), "flac")
    assert captured["timeout"] == 60
