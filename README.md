# local-tts-bookorbit-piper-addon

Local speech for [BookOrbit](https://bookorbit.app). One process, the OpenAI speech API, and the audio stays on the machine that runs it.

It is meant to sit beside BookOrbit in a Proxmox LXC with **2 cores and 4 GB of RAM**. The launchers pin Piper to one thread.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Linux x86_64](https://img.shields.io/badge/platform-linux%20x86__64-lightgrey.svg)](#portable-bundle)
[![BookOrbit](https://img.shields.io/badge/BookOrbit-OpenAI%20TTS-6f42c1.svg)](https://bookorbit.app)

[**Download the tarball**](https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz) ·
[**Connect BookOrbit**](#connect-bookorbit) ·
[**Proxmox tuning**](#proxmox-lxc-2-cores--4-gb) ·
[**Build the portable bundle**](#portable-bundle)

## Start

The tarball is Linux x86_64. Python 3.12.16, Piper, and `en_US-joe-medium` are already in it.

```bash
curl -fL -o local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz \
  https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
tar -xzf local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
cd local-tts-bookorbit-piper-addon
./run.sh
```

From a git checkout, with Python 3.10 or newer:

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon
chmod +x install.sh run.sh build-portable.sh
./install.sh --local --host 127.0.0.1
./run.sh
```

`./run.sh` listens on `http://127.0.0.1:8765`, uses Piper, one thread, and one request at a time. It runs under `nice -n 5` when `nice` is available.

## Connect BookOrbit

An administrator adds the provider on the Text-to-Speech page at `/settings/admin/tts`. These are the form labels in BookOrbit as of commit `851a744`:

| Field | Value |
| --- | --- |
| Name | any name, for example `Local TTS` |
| Base URL | `http://127.0.0.1:8765/v1` |
| API key | leave empty. On a later edit, a blank field keeps the saved key |
| Default model | `tts-1` |
| This provider can list its own voices | leave checked |

Save. On the provider card, use **Test connection**, then **Manage voices** and **Import from provider**.

BookOrbit on the same machine should use `127.0.0.1`. Set `BOOKORBIT_TTS_API_KEY` before binding any other address. The server still starts, and it logs a warning, if that key is missing.

Word highlighting is a second request, `POST /dev/captioned_speech`, on the same host and port with `/v1` taken off the base URL. It uses the same API key as `/v1/audio/speech`.

## Voices

Put Piper voices in [`voices/`](voices/README.md). `./run.sh` scans that folder, including subfolders, and also `data/voices`. `bookorbit-tts download` writes into `data/voices`.

The files are published at [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main). Ryan is under [en/en_US/ryan](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan).

The tarball includes `en_US-joe-medium`. Its [model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/joe/medium/MODEL_CARD) says the dataset is CC0. With `BOOKORBIT_TTS_VOICE` unset, Piper uses that voice when the file is installed, and otherwise the first voice it finds.

Ryan high's [model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ryan/high/MODEL_CARD) says CC BY-NC-SA 4.0. Those files are not in the tarball. Copy them in yourself and restart.

## Word highlighting

BookOrbit posts the speech body to `/dev/captioned_speech` with `stream` false and `return_timestamps` true. The response is JSON: base64 `audio`, and `timestamps` with `word`, `start_time`, and `end_time`. Synthesis is the same work as `/v1/audio/speech`.

If Piper returns a length for each phoneme, those lengths are grouped into words. That return path needs the separate `onnx` package, which this project does not install. Without it, the server splits the clip across the words by character length. There is no second model and no extra thread either way.

The JSON is larger than the MP3 because the audio is base64. BookOrbit requests one sentence at a time.

## Proxmox LXC, 2 cores / 4 GB

Leave the container at 2 cores and 4 GB unless it is already swapping. `./run.sh` sets `BOOKORBIT_TTS_THREADS=1`. The ONNX session then uses that one intra-op thread and one inter-op thread, so another core does not speed Piper up. `nice -n 5` yields when the system is busy.

Kokoro is optional and is not in the tarball. [docker-compose.example.yml](docker-compose.example.yml) limits Piper to 1 CPU and 1 GB, and its comments say to raise that to 2 GB and a second core before enabling Kokoro. `bookorbit-tts serve` with `BOOKORBIT_TTS_ENGINE=auto` keeps an engine when `bookorbit-tts bench` reports at least 1.5× realtime. The launchers set the engine to Piper and skip that check.

## Security

- The default bind is `127.0.0.1`. A non-loopback bind without `BOOKORBIT_TTS_API_KEY` logs a warning and still starts.
- The HTTP API does not download voice files. A requested id has to be a voice that is already installed.
- Request bodies and text length are capped. A full queue returns `429`.
- A synthesis failure is logged on the server. The client receives `synthesis failed`.
- `/docs` is off unless `BOOKORBIT_TTS_DOCS=1`.

The rest is in [SECURITY.md](SECURITY.md).

## Settings

`./run.sh`, the systemd unit, and the tarball set the launcher column. `bookorbit-tts serve` with a bare environment uses the other column.

| Variable | `./run.sh` and the tarball | Bare `serve` |
| --- | --- | --- |
| `BOOKORBIT_TTS_HOST` | `127.0.0.1` | `127.0.0.1` |
| `BOOKORBIT_TTS_PORT` | `8765` | `8765` |
| `BOOKORBIT_TTS_ENGINE` | `piper` | `auto` |
| `BOOKORBIT_TTS_VOICE` | unset. Piper then prefers `en_US-joe-medium` when that file is installed | same |
| `BOOKORBIT_TTS_VOICES_DIR` | `./voices`, also scans `data/voices` | unset, so only `data/voices` |
| `BOOKORBIT_TTS_THREADS` | `1` | `1` |
| `BOOKORBIT_TTS_CONCURRENCY` | `1` | `1` |
| `BOOKORBIT_TTS_API_KEY` | unset | unset |

`/health` does not check the API key. It reports status, version, uptime, engine name, default voice id, voice count, and concurrency. It does not include synthesized text.

## Portable bundle

[Download `local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`](https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz). Python 3.12.16, Piper 1.8.0, and `en_US-joe-medium` are inside. Extract it and run `./run.sh`.

`./build-portable.sh` writes `dist/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`. The script uses `curl` and `tar` to fetch CPython from [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026) (`cpython-3.12.16+20261026-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`), then installs this project and downloads the Joe voice. The ONNX Runtime wheel in that environment is tagged `manylinux_2_28_x86_64`, so the machine that runs the tarball needs glibc 2.28 or newer.

FLAC, Opus, and AAC need `ffmpeg`. Kokoro speed changes use `ffmpeg` `atempo` when `ffmpeg` is installed, and otherwise resample. MP3, WAV, and PCM do not need it.

`systemd/local-tts-bookorbit-piper-addon.service` is the unit file. `sudo ./install.sh --local --host 127.0.0.1 --system-service` installs a system unit. Docker is optional: [docker-compose.example.yml](docker-compose.example.yml) publishes `127.0.0.1:8765` only. That example mounts `./data`, so extra Piper files for it go in `./data/voices`.

## License

GPL-3.0-or-later, the same license as Piper 1.8.0. [LICENSE](LICENSE), [NOTICE](NOTICE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). A voice you add keeps that voice's own license.
