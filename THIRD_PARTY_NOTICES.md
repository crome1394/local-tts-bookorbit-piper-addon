# Third-party notices

`local-tts-bookorbit-piper-addon` is licensed GPL-3.0-or-later. The portable release
bundle includes the components below, each under its own license. This file is
a summary, not legal advice; always check the upstream license for the exact
version you distribute.

## Runtime included in the portable bundle

| Component | Version | License | Source |
| --- | --- | --- | --- |
| Python (python-build-standalone) | 3.12.16 | PSF-2.0 and other licenses | https://github.com/astral-sh/python-build-standalone |
| Piper TTS (`piper-tts`) | 1.8.0 | GPL-3.0-or-later | https://github.com/OHF-Voice/piper1-gpl |
| espeak-ng data bundled with Piper | — | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng |
| ONNX Runtime | 1.31.1 | MIT | https://github.com/microsoft/onnxruntime |
| FastAPI | 0.162.0 | MIT | https://github.com/fastapi/fastapi |
| Uvicorn | 0.54.0 | BSD-3-Clause | https://github.com/encode/uvicorn |
| Starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| Pydantic | 2.14.2 | MIT | https://github.com/pydantic/pydantic |
| NumPy | 2.5.4 | BSD-3-Clause | https://github.com/numpy/numpy |
| lameenc | 1.9.0 | LGPL-3.0-or-later | https://github.com/chrisstaite/lameenc |
| `en_US-joe-medium` Piper voice | — | CC0 1.0 | https://huggingface.co/rhasspy/piper-voices |

The bundled Python distribution also contains OpenSSL, libffi, bzip2, SQLite,
and other runtime libraries. Their license texts are included under
`python/lib/python3.12/` in the extracted bundle, and in the
[python-build-standalone release](https://github.com/astral-sh/python-build-standalone/releases).

## Optional components

These are not part of the default portable bundle:

| Component | License | Notes |
| --- | --- | --- |
| Kokoro-82M / `kokoro-onnx` | Apache-2.0 (model and code; check upstream) | Install with `./install.sh --full` or `BOOKORBIT_TTS_ENGINE=kokoro` |
| `ffmpeg` | LGPL-2.1-or-later or GPL, depending on the build | Needed for FLAC/Opus/AAC output and pitch-preserving Kokoro speed changes |
| Docker base image `python:3.12-slim` | PSF-2.0 and Debian licenses | Only used for the optional Docker build |

## Voice models

Piper voices are separate works with their own dataset licenses. The portable
bundle includes `en_US-joe-medium`, whose model card states **CC0**. Other
voices have different terms:

- `en_US-kristin-medium` and `en_US-norman-medium` — public domain (LibriVox).
- `en_US-hfc_female-medium` — **CC BY-NC-SA 4.0** (non-commercial); not bundled.
- `en_US-ryan-high` — **CC BY-NC-SA 4.0** (non-commercial); not bundled.
- `en_US-lessac-medium` — custom Blizzard/Lessac license; check before
  redistributing.

Always read the `MODEL_CARD` for a voice before shipping it in a product or
release bundle: https://huggingface.co/rhasspy/piper-voices

## GPL source availability

The corresponding source for the GPLv3 components is available at the upstream
links above. The source for this project is the repository that contains this
notice. If you redistribute the portable bundle, keep the license texts, this
notice, and a link to the upstream source with it.
