"""Command line interface: serve, bench, voices, download, doctor."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from . import __version__
from .audio import SUPPORTED
from .config import DEFAULT_PIPER_VOICE, Settings
from .logging_utils import silence_phonemizer
from .onnx_limits import limit_onnx_threads

log = logging.getLogger("bookorbit_tts")


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    for attr in ("host", "port", "engine", "threads", "concurrency", "api_key", "log_level"):
        value = getattr(args, attr, None)
        if value is not None:
            setattr(settings, attr, value)
    voice = getattr(args, "voice", None)
    if voice is not None:
        settings.default_voice = voice
    data_dir = getattr(args, "data_dir", None)
    if data_dir:
        settings.data_dir = Path(data_dir).expanduser()
    return settings


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--engine", choices=["auto", "piper", "kokoro", "espeak"], default=None)
    parser.add_argument("--voice", default=None, help="default voice id")
    parser.add_argument("--data-dir", default=None, help="models and voices directory")
    parser.add_argument("--threads", type=int, default=None, help="ONNX threads (0 = let it choose)")
    parser.add_argument("--concurrency", type=int, default=None, help="parallel synthesis slots")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookorbit-tts",
        description="Low-resource local text-to-speech server for BookOrbit",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run the HTTP server (default)")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--api-key", default=None, help="require this bearer token")
    serve.add_argument("--log-level", default=None)
    _add_common(serve)

    bench = sub.add_parser("bench", help="benchmark installed engines on this machine")
    _add_common(bench)

    voices = sub.add_parser("voices", help="list installed voices")
    _add_common(voices)

    download = sub.add_parser("download", help="download voices/models")
    download.add_argument("voices", nargs="*", help="Piper voice ids (default: %s)" % DEFAULT_PIPER_VOICE)
    download.add_argument("--kokoro", action="store_true", help="also download the Kokoro model")
    _add_common(download)

    doctor = sub.add_parser("doctor", help="check the installation and run a test synthesis")
    _add_common(doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"
    try:
        settings = _settings(args)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(
        level=getattr(logging, str(settings.log_level).upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )
    silence_phonemizer()
    limit_onnx_threads(settings.threads)

    if command == "serve":
        return _serve(settings)
    if command == "bench":
        return _bench(settings)
    if command == "voices":
        return _voices(settings)
    if command == "download":
        return _download(settings, args)
    if command == "doctor":
        return _doctor(settings)
    parser.error(f"unknown command {command}")
    return 2


def _serve(settings: Settings) -> int:
    import uvicorn

    from .server import create_app

    app = create_app(settings)
    level = "info" if settings.log_level not in {"warning", "warn", "error"} else settings.log_level
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=level, access_log=False)
    return 0


def _bench(settings: Settings) -> int:
    from .engines import benchmark, make_engines

    engines = make_engines(settings)
    if not engines:
        print("No usable engines. Run `bookorbit-tts doctor` or `bookorbit-tts download`.")
        return 1
    if settings.engine != "auto":
        if settings.engine not in engines:
            print(f"Engine {settings.engine!r} is not available; installed: {', '.join(sorted(engines))}")
            return 1
        engines = {settings.engine: engines[settings.engine]}
    print(f"Benchmarking on this machine (threads={settings.threads or 'auto'}):\n")
    print(f"{'engine':<10} {'real-time factor':>18}  {'verdict':<10}")
    print("-" * 44)
    rows = []
    for name in sorted(engines, key=lambda key: engines[key].quality, reverse=True):
        engine = engines[name]
        rtf = benchmark(engine, voice_id=settings.default_voice)
        verdict = "usable" if rtf >= settings.auto_min_rtf else ("slow" if rtf > 0 else "failed")
        rows.append((engine.quality, name, rtf, verdict))
        print(f"{name:<10} {rtf:>16.1f}x  {verdict:<10}")
        engine.close()
    usable = [row for row in rows if row[2] >= settings.auto_min_rtf]
    pick = max(usable, key=lambda row: row[0]) if usable else max(rows, key=lambda row: row[2])
    print(f"\nRecommended: {pick[1]} ({pick[2]:.1f}x real time)")
    if len(rows) == 1:
        print(f"Start with: bookorbit-tts serve --engine {pick[1]}")
    else:
        print("Start with: bookorbit-tts serve --engine auto")
    return 0


def _voices(settings: Settings) -> int:
    from .engines import make_engines

    engines = make_engines(settings)
    if not engines:
        print("No voices installed. Run `bookorbit-tts download`.")
        return 1
    for engine_name, engine in engines.items():
        voices = engine.voices()
        print(f"\n{engine_name} ({len(voices)} voices)")
        for voice in voices:
            print(f"  {voice.id:<32} {voice.name:<20} {voice.language:<12} {voice.gender}")
    return 0


def _download(settings: Settings, args: argparse.Namespace) -> int:
    from .engines import download_kokoro, download_piper_voices

    settings.ensure_dirs()
    wanted = args.voices or [settings.default_voice or DEFAULT_PIPER_VOICE]
    print(f"Downloading Piper voices into {settings.voices_dir}: {', '.join(wanted)}")
    done = download_piper_voices(list(wanted), settings.voices_dir)
    if args.kokoro:
        print(f"Downloading Kokoro model into {settings.kokoro_dir} (~140 MB)")
        download_kokoro(settings)
    print(f"Done. Installed {len(done)} Piper voice(s).")
    return 0


def _doctor(settings: Settings) -> int:
    import platform

    from .engines import make_engines, select_engine

    print(f"bookorbit-tts {__version__}")
    print(f"python          {platform.python_version()} ({sys.executable})")
    print(f"data dir        {settings.data_dir}")
    print(f"voices dir      {settings.voices_dir}")
    print(f"ffmpeg          {shutil.which('ffmpeg') or 'missing (flac/opus/aac unavailable)'}")
    print(f"espeak-ng       {shutil.which('espeak-ng') or 'missing'}")
    print(f"output formats  {', '.join(SUPPORTED)}")
    try:
        import onnxruntime

        print(f"onnxruntime     {onnxruntime.__version__}")
    except ImportError:
        print("onnxruntime     missing")
    try:
        import kokoro_onnx  # noqa: F401

        print("kokoro-onnx     installed")
    except ImportError:
        print("kokoro-onnx     not installed (piper only)")
    engines = make_engines(settings)
    print(f"engines         {', '.join(engines) or 'none'}")
    if not engines:
        print("\nNo engine available. Install one with `bookorbit-tts download`.")
        return 1
    try:
        from .synthesizer import Synthesizer

        engine, scores = select_engine(settings)
        synth = Synthesizer(engine, settings)
        sample = synth.speak("BookOrbit text to speech is working.", None, 1.0, "wav")
        print(f"test synthesis  {len(sample)} bytes with {engine.name}")
        print(f"scores          {scores or 'explicit engine'}")
        print(f"\nReady. BookOrbit base URL: http://<this-host>:{settings.port}/v1")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\nTest synthesis failed: {exc}")
        return 1
