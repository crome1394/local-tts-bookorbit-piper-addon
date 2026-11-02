# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The README quick start clones the repository. The portable tarball is built
  with `./build-portable.sh`. A GitHub release asset is not attached yet.
- Clone instructions run `chmod +x` on the shell scripts before `./install.sh`.

## [0.1.1] - 2026-11-01

Security and resource review for a 2-core / 4 GB LXC shared with BookOrbit.

### Security

- Request bodies are rejected once they pass a small cap, before JSON decoding.
- The API key is compared from SHA-256 digests. Oversized `Authorization` headers are rejected.
- Synthesis failures returned to the client no longer include paths or tracebacks.
- Voice ids from clients must match a short token pattern. `download` accepts only a Piper voice id, so a name cannot escape the voices directory.
- Kokoro downloads are HTTPS-only, size-capped, and written via a temporary file.
- espeak-ng receives the sentence after `--`, so text cannot be read as `-f` or `-w`.
- `install.sh` refuses host, port, and voice values that would change the systemd unit.
- The Docker image runs as uid 10001. The Compose example publishes `127.0.0.1:8765` only, drops capabilities, and limits the container to 1 CPU and 1 GB.
- `/docs` stays off unless `BOOKORBIT_TTS_DOCS=1`.
- Binding a non-loopback address without `BOOKORBIT_TTS_API_KEY` logs a warning.

### Fixed

- Replacing a cache entry counted its bytes twice, so the cache could grow past `CACHE_MB`.
- `auto` could keep a rejected engine's model resident, and could hand back an engine it had already closed.
- A single token with no spaces could skip the per-chunk character limit.
- `ffmpeg` waits at most 60 seconds.
- A missing Piper voice is reported instead of silently speaking a different one.
- `./run.sh` and the installer service default to Piper, matching the portable bundle. `auto` no longer benchmarks on every start of those launchers.

### Changed

- Public name is `local-tts-bookorbit-piper-addon`.
- Threads, concurrency, queue length, cache size, bitrate, and text length have hard ceilings.
- When the synthesis queue is full, or a waiter exceeds `WAIT_TIMEOUT`, the server returns `429`.
- ONNX sessions use one inter-op thread, sequential execution, and no memory-pattern cache.

## [0.1.0] - 2026-11-01

First public release.

### Added

- OpenAI-compatible TTS server for BookOrbit with `/v1/models`,
  `/v1/audio/voices`, `/v1/audio/speech`, and `/health`.
- Piper engine tuned for small machines: one ONNX thread, one request at a
  time, and `nice 5` in the portable launcher.
- Optional Kokoro-82M engine for machines with spare CPU.
- `espeak-ng` fallback for tiny installations.
- `auto` engine selection based on a startup real-time-factor benchmark.
- In-memory MP3, WAV, and PCM encoding; no audio files are written by the TTS
  server. Synthesized audio is kept in a size-limited in-process LRU cache.
- Pitch-preserving speed control for Kokoro through `ffmpeg atempo`, covering
  BookOrbit's 0.25x–4x range.
- Portable Linux x86_64 bundle containing Python, dependencies, the server, and
  a CC0 Piper voice. No Docker, system Python, pip, or root required.
- Source installer with local data mode, systemd user service, and systemd
  system service options.
- Optional Dockerfile and Compose example.
- Documentation for running beside BookOrbit in a 2-core / 4 GB Proxmox LXC.
- Unit tests for the API, audio encoding, and text handling.

### Changed

- The public release bundles `en_US-joe-medium` (CC0) as the default Piper
  voice. The previous local default, `en_US-hfc_female-medium`, is still
  supported but is licensed CC BY-NC-SA 4.0 and is therefore not included in
  the public bundle.
- The project is licensed GPL-3.0-or-later to match the bundled Piper engine
  and espeak-ng data.

### Notes

- BookOrbit's optional captioned-speech endpoint is intentionally not
  implemented, so word-by-word highlighting is unavailable. Normal audio
  playback is unaffected.
- Voice models have their own licenses. See
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before redistributing a
  voice.
