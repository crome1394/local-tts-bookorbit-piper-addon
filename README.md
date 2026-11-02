# local-tts-bookorbit-piper-addon

**Give BookOrbit a natural voice — locally, privately, on hardware you already own.**

A tiny **OpenAI-compatible text-to-speech server** built for
[BookOrbit](https://bookorbit.app). It runs beside BookOrbit in a
**2-core / 4 GB Proxmox LXC**, uses **one ONNX thread** and about **250 MB RAM**,
and never sends your books to a cloud service.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Linux x86_64](https://img.shields.io/badge/platform-linux%20x86__64-lightgrey.svg)](#portable-bundle)
[![BookOrbit](https://img.shields.io/badge/BookOrbit-OpenAI%20TTS-6f42c1.svg)](https://bookorbit.app)

[**Connect BookOrbit**](#connect-bookorbit) ·
[**Proxmox tuning**](#proxmox-lxc-2-cores--4-gb) ·
[**Build the portable bundle**](#portable-bundle)

---

## The 30-second version

BookOrbit already has an OpenAI-compatible TTS provider. This project is the
missing local endpoint: one portable directory, one process, and a natural
Piper voice.

- **No Docker.** The release tarball contains its own Python, dependencies, and
  voice.
- **No cloud.** Book text and audio never leave your machine.
- **No GPU.** CPU-only inference, one thread by default.
- **No API keys.** BookOrbit talks to `http://127.0.0.1:8765/v1`.
- **No audio files on disk.** MP3/WAV/PCM data is encoded and cached in RAM.
- **No BookOrbit patch.** It implements the same `/v1` endpoints BookOrbit
  already uses for OpenAI TTS.

### Quick start

From a clone (Python 3.10+):

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon
chmod +x install.sh run.sh build-portable.sh
./install.sh --local --host 127.0.0.1
./run.sh
```

That starts the server on `http://127.0.0.1:8765`, using Piper, one ONNX thread,
one request at a time, and `nice 5` so BookOrbit keeps priority.

A vanilla LXC does not need a system Python. Build the self-contained tarball
with `./build-portable.sh` (see [Portable bundle](#portable-bundle)), copy it
into the container, and run `./run.sh` from the extracted directory. A GitHub
release asset is not attached yet.

Then add the provider in BookOrbit:

| Field | Value |
| --- | --- |
| Name | `Local TTS` |
| Base URL | `http://127.0.0.1:8765/v1` |
| Model | `tts-1` |
| API key | leave empty |
| Voice discovery | on |

Save, press **Test**, then choose a voice under **Settings → TTS**.

---

## Why this exists

Cloud TTS is convenient until you have a 900-page book, a slow connection, or a
privacy requirement. Piper is fast enough to run on a mini PC, but wiring it
into BookOrbit usually means Docker, a Python environment, or a service to
babysit.

This add-on is deliberately small:

- **One process.** A FastAPI server exposes the three endpoints BookOrbit
  needs: `/v1/models`, `/v1/audio/voices`, and `/v1/audio/speech`.
- **One directory.** The portable bundle includes Python 3.12, all Python
  dependencies, the server, and a CC0 Piper voice. Remove the directory to
  uninstall.
- **One core.** `THREADS=1` and `CONCURRENCY=1` leave the second core for
  BookOrbit and the OS. `nice 5` keeps the server polite during playback.
- **One job.** It does not manage your library, scan books, or write audio
  files. BookOrbit remains the source of truth.

The server is tested against BookOrbit's OpenAI-compatible TTS provider. It also
works with any other client that speaks the same API.

---

## Performance

The table below was measured on a Ryzen 9 9950X3D with two cores pinned and
one ONNX thread. This add-on is aimed at a smaller box: an HP EliteDesk 800 G6
(i7-10700) with BookOrbit and the TTS server sharing a **2-core / 4 GB**
Proxmox LXC. The integrated UHD 630 is unused; the build is CPU-only. On the i7-10700 host,
one thread of `en_US-hfc_female-medium` measured **31.2x** realtime, in line
with the Ryzen figure for a medium voice. Run `bench` inside the LXC before
you change engines. Kokoro's 1.8x figure is from the faster desktop CPU and
should be rechecked there.

| Engine | Threads | Real-time factor | Memory | Notes |
| --- | ---: | ---: | ---: | --- |
| **Piper medium** | 1 | **~33x** | ~250 MB | Default; excellent for a 2-core LXC |
| Piper `en_US-ryan-high` | 1 | ~4.4x | ~250 MB | Fuller male voice; much heavier |
| **Kokoro int8** | 2 | **~1.8x** | ~400 MB | Optional; more natural, uses both cores |
| `espeak-ng` | 1 | ~1300x | tiny | Robotic fallback |

Piper medium is the safe default. Kokoro is worth testing only if you can give
it a second thread and it reports **≥ 1.5x** on your hardware:

```bash
BOOKORBIT_TTS_THREADS=2 ./.venv/bin/bookorbit-tts bench --engine kokoro
```

If it reports less, stay with Piper. BookOrbit caches each synthesized sentence,
so even ~2x is usable, but Kokoro will compete with BookOrbit for both cores.

---

## Compared with the other Piper options

Three things get called "the Piper add-on." They solve different jobs.

| | This add-on | Piper's HTTP server | BookOrbit's Kokoro profile | Home Assistant Piper add-on |
| --- | --- | --- | --- | --- |
| What it is | OpenAI-compatible server plus a portable tarball | `python -m piper.http_server` in `piper-tts` | `ghcr.io/remsky/kokoro-fastapi-cpu` in BookOrbit's Compose file | Wyoming service for Home Assistant |
| BookOrbit | Provider base URL ends in `/v1` | Different JSON and paths (`/synthesize`) | Supported provider | Wyoming, so BookOrbit cannot use it |
| Install beside BookOrbit in an LXC | Extract the tarball. No Docker | A Python environment and a voice download | A container image | Home Assistant only |
| Default listen address | `127.0.0.1:8765` | `0.0.0.0:5000` | Compose network, port not published | Home Assistant's network |
| Authentication | Optional bearer token | None | None on that network | Home Assistant's own controls |
| Voice download from the API | No. `bookorbit-tts download` only | `POST /download`, no authentication | No | No |
| CPU use | 1 ONNX thread, 1 request, `nice 5` | ONNX uses every visible core | Designed to use more than one core | Tuned for Assist, not a shared BookOrbit LXC |
| Memory | About 250 MB for one medium voice | One voice, and it keeps phoneme alignments | About 400 MB and a much larger image | About the same as Piper |
| Audio BookOrbit asks for | MP3, encoded in memory | WAV | MP3 or WAV | Audio over Wyoming |
| Word highlighting | Not provided | Phoneme timings for its own page | Not provided | Not provided |

On the 2-core / 4 GB LXC, Piper medium is the one that leaves a core and most of the RAM for BookOrbit. Kokoro sounds more natural. Use it when `bench` on that LXC reports at least 1.5x with two threads. The UHD 630 does not accelerate the default ONNX Runtime build, so there is no GPU path to turn on.

Piper's own HTTP server is a useful demo of the engine. It is the wrong process to point BookOrbit at: the paths differ, it binds every interface, it will download a voice for anyone who can POST, and it does not cap text length, concurrency, or threads. This add-on keeps Piper and adds the limits a shared container needs.

---

## Security

The server is meant to run next to BookOrbit on localhost.

- The default bind is `127.0.0.1`. Set `BOOKORBIT_TTS_API_KEY` before you use `0.0.0.0`. Startup logs a warning when the bind address is not loopback and no key is set.
- Nothing in the HTTP API downloads a voice or reads a file. Voice ids from clients have to match an installed voice. `bookorbit-tts download` accepts only a Piper voice id such as `en_US-joe-medium`.
- Request bodies are capped (64 KB, or a bit more if you raise the text limit). Text longer than `MAX_TEXT_CHARS` is rejected. The hard ceiling is 20,000 characters. A full queue returns `429` instead of lining up without bound.
- A synthesis failure is logged on the server. The client receives `synthesis failed`, without paths or tracebacks.
- `/docs` is off unless `BOOKORBIT_TTS_DOCS=1`.
- The optional container runs as uid 10001, drops capabilities, and the example Compose file publishes `127.0.0.1:8765` only. Give that uid write access to the data directory: `sudo chown 10001:10001 data`.

See [SECURITY.md](SECURITY.md) for the threat model.

---

## Portable bundle

**Recommended for a vanilla LXC.**

The release tarball is a self-contained Linux x86_64 directory:

- Python 3.12.16
- FastAPI, Uvicorn, ONNX Runtime, Piper, and the default CC0 voice
- the TTS server itself
- no system Python, pip, virtualenv, Docker, or apt packages required

Build it on a machine with `curl`, `tar`, and `espeak-ng`:

```bash
chmod +x build-portable.sh
./build-portable.sh
```

The script writes `dist/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`.
Copy that file into the LXC, then:

```bash
tar -xzf local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
cd local-tts-bookorbit-piper-addon
./run.sh
```

When a GitHub release is attached, the same archive is also at:

```bash
curl -L -o local-tts-bookorbit-piper-addon.tar.gz \
  https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
```

The bundle is about **174 MB compressed** and **376 MB extracted** (the exact
size depends on the bundled voice). It works on Debian 10+, Ubuntu 20.04+, and
Proxmox Debian 12 (glibc 2.28 or newer). MP3, WAV, and PCM work out of the box.
Install `ffmpeg` only if you need FLAC, Opus, AAC, or pitch-preserving Kokoro
speed changes.

`run.sh` defaults:

```text
host        127.0.0.1
port        8765
engine      piper
threads     1
concurrency 1
priority    nice 5
data        ./data
```

Override any of them in the environment:

```bash
BOOKORBIT_TTS_PORT=9000 BOOKORBIT_TTS_HOST=0.0.0.0 ./run.sh
```

To start it at boot, use one systemd unit:

```ini
[Unit]
Description=local-tts-bookorbit-piper-addon
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/local-tts-bookorbit-piper-addon
ExecStart=/opt/local-tts-bookorbit-piper-addon/run.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now local-tts-bookorbit-piper-addon
```

No root is required to run the bundle itself; it listens on port 8765 as an
unprivileged user. Root is only needed if you install a system service.

---

## Source install

Use this if you want to develop, use Kokoro, or manage the Python environment
yourself.

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon
chmod +x install.sh run.sh build-portable.sh

./install.sh --local --host 127.0.0.1
./run.sh
```

`--local` keeps the voice model in `./data`, so the whole installation stays in
one directory. `./run.sh` binds `127.0.0.1:8765`, uses one thread and `nice 5`.

For Kokoro as well:

```bash
./install.sh --full --local --host 127.0.0.1
BOOKORBIT_TTS_ENGINE=kokoro BOOKORBIT_TTS_THREADS=2 ./run.sh
```

### systemd service

User service:

```bash
./install.sh --local --host 127.0.0.1 --service --no-install
loginctl enable-linger "$USER"
```

System service, as root:

```bash
./install.sh --local --host 127.0.0.1 --system-service --no-install
```

### Docker (optional)

Docker is not required, and it is not the recommended path for a small LXC.

```bash
docker build -t local-tts-bookorbit-piper-addon .
docker run -d --name local-tts-bookorbit-piper-addon \
  -p 8765:8765 \
  -v "$PWD/data:/data" \
  local-tts-bookorbit-piper-addon
```

For Kokoro, build with `--build-arg EXTRAS="[kokoro]"` and download the model
once:

```bash
docker exec local-tts-bookorbit-piper-addon bookorbit-tts download --kokoro
```

`docker-compose.example.yml` joins an existing `bookorbit_default` network. The
provider URL then becomes `http://local-tts-bookorbit-piper-addon:8765/v1`.

---

## Connect BookOrbit

**Settings → Admin → Text to Speech → Add provider**

| Field | Value |
| --- | --- |
| Name | `Local TTS` |
| Base URL | `http://127.0.0.1:8765/v1` |
| Model | `tts-1` |
| API key | leave empty (unless you set `BOOKORBIT_TTS_API_KEY`) |
| Voice discovery | on |

Save, press **Test**, then pick a voice under **Settings → TTS**.

If BookOrbit is in a **different** LXC or VM, start the server on all
interfaces:

```bash
BOOKORBIT_TTS_HOST=0.0.0.0 ./run.sh
```

Then use the TTS container's bridge IP, for example
`http://192.168.1.42:8765/v1`. Do not use `127.0.0.1` from another container.

Verify the connection from the BookOrbit host:

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/v1/models
```

---

## Proxmox LXC (2 cores / 4 GB)

This is the target shape: BookOrbit and the TTS server share a 2-core / 4 GB
LXC. No GPU, sound card, or special privileges are needed.

| Engine | Threads | Memory | Recommendation |
| --- | ---: | ---: | --- |
| Piper medium | 1 | ~250 MB | **Use this**; leaves a core for BookOrbit |
| Piper `ryan-high` | 1 | ~250 MB | Test first; ~4x real time |
| Kokoro int8 | 2 | ~400 MB+ | Test first; uses both cores |
| espeak-ng | 1 | tiny | Fallback only |

Typical setup:

1. Create a Debian 12 LXC with **2 cores**, **4 GB RAM**, and **8 GB disk**.
2. Copy the portable tarball into the container and extract it in
   `/opt/local-tts-bookorbit-piper-addon` (or any writable directory).
3. Run `./run.sh` as a normal user, or install the optional systemd unit.
4. In BookOrbit, use `http://127.0.0.1:8765/v1` because both services share the
   container's network namespace.

The defaults are intentionally conservative:

- one ONNX intra-op thread
- one simultaneous synthesis request
- `nice 5`
- 32 MB in-memory audio cache
- no audio files written to disk

If you use **Kokoro**, benchmark it inside the LXC before committing:

```bash
cd /opt/local-tts-bookorbit-piper-addon
BOOKORBIT_TTS_THREADS=2 ./python/bin/bookorbit-tts bench --engine kokoro
```

If the result is **≥ 1.5x**, opt in:

```bash
BOOKORBIT_TTS_ENGINE=kokoro BOOKORBIT_TTS_THREADS=2 ./run.sh
```

Otherwise, Piper is the better neighbor.

### A note on disk and RAM

The TTS server itself writes **no MP3s**. It synthesizes into memory, encodes
MP3 bytes in memory, and keeps a size-limited LRU cache in process memory. The
`mp3` at the end of a `synthesized ...` log line is the response format, not a
file.

BookOrbit's normal TTS cache is also memory-only. If you see MP3 files on disk,
they are likely from a different feature, such as BookOrbit's **Create
read-aloud** alignment jobs (which copy/process audiobook tracks) or your
library's own audiobook files. Those are user data, not TTS cache; keep them on
disk unless you have a specific reason to use a RAM-backed temporary directory.

To retain more synthesized audio in memory:

```bash
BOOKORBIT_TTS_CACHE_MB=128 ./run.sh
```

This does not change disk usage; it only keeps more clips available for replay.

---

## Voices

The public bundle ships with **`en_US-joe-medium`**, a CC0 male voice. It is a
good default that can be redistributed without restrictions.

Good alternatives:

| Voice | Character | License | Notes |
| --- | --- | --- | --- |
| `en_US-joe-medium` | Male, natural | **CC0** | Bundled default |
| `en_US-kristin-medium` | Female, LibriVox | **Public domain** | Download separately |
| `en_US-norman-medium` | Male, LibriVox | **Public domain** | Download separately |
| `en_US-hfc_female-medium` | Female, natural | **CC BY-NC-SA 4.0** | Non-commercial; not bundled |
| `en_US-ryan-high` | Male, fuller prosody | **CC BY-NC-SA 4.0** | Non-commercial; much heavier |
| `en_US-lessac-medium` | Neutral | Custom Blizzard/Lessac license | Check before redistributing |

Voice licenses are separate from the code license. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the
[Piper voices repository](https://huggingface.co/rhasspy/piper-voices) before
redistributing a voice.

Download another voice:

```bash
# Source install
.venv/bin/bookorbit-tts download en_US-kristin-medium

# Portable bundle
./python/bin/bookorbit-tts download en_US-kristin-medium
```

Select it:

```bash
BOOKORBIT_TTS_VOICE=en_US-kristin-medium ./run.sh
```

The `--voice` flag works with `bookorbit-tts serve` and `bookorbit-tts bench` as
well.

---

## Configuration

All settings are environment variables with the `BOOKORBIT_TTS_` prefix.

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | bind address |
| `PORT` | `8765` | HTTP port |
| `ENGINE` | `auto` (launchers set `piper`) | `auto`, `piper`, `kokoro`, `espeak` |
| `VOICE` | engine default | default voice id |
| `DATA_DIR` | `~/.local/share/bookorbit-tts` | voices and models |
| `THREADS` | `1` | ONNX intra-op threads, 0–8. `0` uses every visible core |
| `CONCURRENCY` | `1` | simultaneous synthesis requests, 1–4 |
| `QUEUE` | `4` | requests allowed to wait; `0` rejects as soon as the server is busy |
| `WAIT_TIMEOUT` | `60` | seconds a queued request waits for a free slot (1–120) |
| `AUTO_MIN_RTF` | `1.5` | minimum real-time factor for `auto` |
| `API_KEY` | empty | require `Authorization: Bearer ...` |
| `CACHE_MB` | `32` | in-memory audio cache, 0–256 |
| `MP3_BITRATE` | `64` | kbps, mono, 16–320 |
| `MAX_TEXT_CHARS` | `4000` | reject longer requests; hard ceiling 20000 |
| `LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error` |
| `DOCS` | off | set to `1` to enable `/docs` |

`run.sh` sets the small-machine defaults for you: localhost, port 8765, Piper,
one thread, one request, `nice 5`, and `./data` when present.

`auto` benchmarks the installed engines and picks the most natural one that can
still synthesize faster than real time. With `THREADS=1`, it skips Kokoro and
selects Piper without loading the heavier model.

---

## API

The server exposes the endpoints BookOrbit needs:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | health and current engine |
| `GET` | `/v1/models` | connection test |
| `GET` | `/v1/audio/voices` | voice catalogue |
| `POST` | `/v1/audio/speech` | synthesis |

Example:

```bash
curl http://localhost:8765/health

curl -X POST http://localhost:8765/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "tts-1",
    "input": "Hello from BookOrbit.",
    "voice": "en_US-joe-medium",
    "speed": 1.0,
    "response_format": "mp3"
  }' \
  -o speech.mp3
```

`response_format` accepts `mp3`, `wav`, `pcm`, `flac`, `opus`, and `aac`.
MP3 and WAV need no external tools; the others use `ffmpeg` when installed.

BookOrbit's optional captioned-speech endpoint is intentionally **not**
implemented, so word-by-word highlighting is unavailable. Normal playback is
unaffected.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| BookOrbit says *connection failed* | Run `curl http://127.0.0.1:8765/v1/models` from the BookOrbit host. Check the port, the container network, and that the URL ends in `/v1`. |
| Voice list is empty | Run `bookorbit-tts voices`; download a voice with `bookorbit-tts download …`. |
| Health works but synthesis fails | Run `bookorbit-tts doctor`; usually a missing or corrupt ONNX model. |
| Playback stutters | Run `bookorbit-tts bench`; use Piper or a smaller voice. Check that `THREADS=1` and `CONCURRENCY=1`. |
| Audio is too slow or fast | Set the speed in BookOrbit; the server accepts 0.25x–4x. |
| `503` responses | The engine is not ready or the model failed to load; check the server log and `doctor`. |
| `GLIBC_2.28 not found` | The portable bundle needs Debian 10+/Ubuntu 20.04+ or newer. |
| Port 8765 already in use | Set `BOOKORBIT_TTS_PORT` for both the server and BookOrbit's base URL. |
| Permission denied on the tarball | Extract it into a directory your user can write to; do not run the whole bundle as root unless you need a system service. |

Enable debug logging when reporting a problem:

```bash
BOOKORBIT_TTS_LOG_LEVEL=debug ./run.sh
```

---

## Development

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon

python3 -m venv .venv
.venv/bin/pip install -e '.[kokoro,test]'
.venv/bin/python -m pytest
.venv/bin/bookorbit-tts serve --log-level debug
```

Build the portable bundle:

```bash
chmod +x build-portable.sh
./build-portable.sh
```

It downloads a pinned python-build-standalone release, installs the project and
dependencies into `dist/`, downloads the default voice, starts the bundle on a
test port, checks health and MP3 synthesis, and writes:

```text
dist/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
```

The build is deterministic in layout, but the exact tarball bytes depend on the
Python build and dependency versions.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## License

`local-tts-bookorbit-piper-addon` is licensed **GPL-3.0-or-later**. The default Piper
engine (`piper-tts` 1.8) and the espeak-ng data it bundles are GPLv3, so a
GPLv3-compatible release is the honest choice for this distribution.

- [LICENSE](LICENSE) — full GPLv3 text
- [NOTICE](NOTICE) — copyright and warranty notice
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — bundled components and
  voice-model licenses

The code license does **not** automatically cover voice models. Check each
voice's model card before redistributing it. The portable release bundles
`en_US-joe-medium`, which is CC0.

If you want a permissive license for a fork, you would need to replace the
GPLv3 Piper engine with a permissive engine and review the bundled espeak-ng
data; do not simply relabel this bundle as MIT.
