# local-tts-bookorbit-piper-addon

Local Piper speech for [BookOrbit](https://bookorbit.app). One process, the OpenAI speech API BookOrbit already speaks, and the audio stays on the machine.

It is meant to run beside BookOrbit in a Proxmox LXC with **2 cores and 4 GB of RAM**. Piper uses one thread.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Linux x86_64](https://img.shields.io/badge/platform-linux%20x86__64-lightgrey.svg)](#portable-bundle)
[![BookOrbit](https://img.shields.io/badge/BookOrbit-OpenAI%20TTS-6f42c1.svg)](https://bookorbit.app)

[**Download the tarball**](https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz) ·
[**Connect BookOrbit**](#connect-bookorbit) ·
[**Proxmox tuning**](#proxmox-lxc-2-cores--4-gb) ·
[**Build the portable bundle**](#portable-bundle)

## Start

Download the tarball, extract it, and run it. No system Python:

```bash
curl -fL -o local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz \
  https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
tar -xzf local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz
cd local-tts-bookorbit-piper-addon
./run.sh
```

From a git checkout (Python 3.10 or newer):

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon
chmod +x install.sh run.sh build-portable.sh
./install.sh --local --host 127.0.0.1
./run.sh
```

The server listens on `http://127.0.0.1:8765`. Piper, one thread, one request at a time, `nice 5`.

## Connect BookOrbit

| Field | Value |
| --- | --- |
| Name | `Local TTS` |
| Base URL | `http://127.0.0.1:8765/v1` |
| Model | `tts-1` |
| API key | leave empty |
| Voice discovery | on |

Save, press **Test**, then pick a voice under **Settings → TTS**.

BookOrbit and this server share the container, so `127.0.0.1` is the right address. Set `BOOKORBIT_TTS_API_KEY` before binding `0.0.0.0`.

## Voices

Put voices in [`voices/`](voices/README.md). Download them from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main). Ryan is [en/en_US/ryan](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan). Keep the folder layout, or copy the pair anywhere under `voices/`:

```text
voices/en/en_US/ryan/high/en_US-ryan-high.onnx
voices/en/en_US/ryan/high/en_US-ryan-high.onnx.json
```

Both files are required. The name has to be a Piper id such as `en_US-ryan-high`. Restart after adding a voice. `./data/voices` is scanned too; `bookorbit-tts download` writes there.

The portable bundle includes `en_US-joe-medium` (CC0). Other voices keep their own licenses. Ryan high is CC BY-NC-SA 4.0 and is not in the public bundle.

Ryan high, one thread, model already loaded: about **4.4× realtime** and about **370 MB**. A medium voice is faster and smaller. Either fits this LXC.

## Word highlighting

BookOrbit highlights words when the server answers `POST /dev/captioned_speech` with the audio and a time for each word. That is the same synthesis as `/v1/audio/speech`. Piper already knows how long each phoneme is; the server groups those phonemes into words. There is no second model and no extra core.

The JSON body is larger than a raw MP3 because the audio is base64. One sentence at a time, that is noise next to the voice model.

## Proxmox LXC, 2 cores / 4 GB

Leave the container at 2 cores and 4 GB unless it is already swapping. Piper is pinned to one thread, so another core does not make it faster. BookOrbit keeps the other core. `nice 5` keeps speech from competing with page turns.

Kokoro is optional and wants both cores and about 400 MB. Use it only when this reports at least 1.5×:

```bash
BOOKORBIT_TTS_THREADS=2 ./.venv/bin/bookorbit-tts bench --engine kokoro
```

## Security

- Default bind is `127.0.0.1`. A non-loopback bind without an API key logs a warning.
- Voice download is not on the HTTP API. A client voice id has to match an installed voice.
- Request bodies and text length are capped. A full queue returns `429`.
- A failed synthesis is logged on the server. The client gets `synthesis failed`.
- `/docs` is off unless `BOOKORBIT_TTS_DOCS=1`.

Details are in [SECURITY.md](SECURITY.md).

## Settings

| Variable | Default | What it does |
| --- | --- | --- |
| `BOOKORBIT_TTS_HOST` | `127.0.0.1` | Bind address |
| `BOOKORBIT_TTS_PORT` | `8765` | Listen port |
| `BOOKORBIT_TTS_ENGINE` | `piper` | `piper`, `kokoro`, `espeak`, or `auto` |
| `BOOKORBIT_TTS_VOICE` | first installed Piper voice | Voice id |
| `BOOKORBIT_TTS_VOICES_DIR` | `./voices` | Drop folder for Piper models |
| `BOOKORBIT_TTS_THREADS` | `1` | ONNX threads. Keep this at 1 in the shared LXC |
| `BOOKORBIT_TTS_CONCURRENCY` | `1` | Syntheses at once |
| `BOOKORBIT_TTS_API_KEY` | unset | Bearer token for `/v1/*` and captioned speech |

`/health` stays open so a local probe can run. It does not include the text you synthesized.

## Portable bundle

[Download `local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`](https://github.com/crome1394/local-tts-bookorbit-piper-addon/releases/latest/download/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz). It contains Python 3.12, Piper, and `en_US-joe-medium`. Extract it and run `./run.sh`. No system Python, pip, or Docker.

To build that same archive yourself, `./build-portable.sh` writes `dist/local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`.

```bash
chmod +x build-portable.sh
./build-portable.sh
```

Needs `curl`, `tar`, and `espeak-ng` on the build machine. The result runs on glibc 2.28 or newer (Debian 10+, Ubuntu 20.04+, Proxmox Debian 12).

Install `ffmpeg` only for FLAC, Opus, AAC, or Kokoro speed changes. MP3, WAV, and PCM are built in.

A systemd unit is in `systemd/local-tts-bookorbit-piper-addon.service`. `./install.sh --local --host 127.0.0.1 --system-service` installs one. Docker is optional; see `docker-compose.example.yml`. It publishes `127.0.0.1:8765` only.

## License

GPL-3.0-or-later, the same license as Piper. [LICENSE](LICENSE), [NOTICE](NOTICE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Voice models you add are not covered by that license.
