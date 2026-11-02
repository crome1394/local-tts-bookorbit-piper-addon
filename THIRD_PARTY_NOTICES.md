# Third-party notices

This project is GPL-3.0-or-later. See [LICENSE](LICENSE) and [NOTICE](NOTICE). The portable tarball also contains the pieces below. Versions and license expressions are taken from the packages in `local-tts-bookorbit-piper-addon-linux-x86_64.tar.gz`. This file is a pointer, not a substitute for the upstream license.

## In the portable tarball

| Component | Version | License expression in the package | Where it came from |
| --- | --- | --- | --- |
| CPython, python-build-standalone `install_only_stripped` | 3.12.16, tag `20261026` | several; the texts are under `python/lib/python3.12/` in the tarball | https://github.com/astral-sh/python-build-standalone/releases/tag/20261026 |
| Piper (`piper-tts`) | 1.8.0 | GPL-3.0-or-later | http://github.com/OHF-voice/piper1-gpl |
| espeak-ng data shipped inside that Piper package | — | see the Piper package; the files are `piper/espeak-ng-data/` | https://github.com/espeak-ng/espeak-ng |
| ONNX Runtime | 1.31.1 | MIT | https://onnxruntime.ai |
| FastAPI | 0.162.0 | MIT | https://github.com/fastapi/fastapi |
| Uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev |
| Starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| Pydantic | 2.14.2 | MIT | https://github.com/pydantic/pydantic |
| NumPy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| lameenc | 1.9.0 | LGPL-3.0-or-later | https://github.com/chrisstaite/lameenc |
| `en_US-joe-medium` | — | dataset CC0, from its model card | https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/joe/medium/MODEL_CARD |

The ONNX Runtime wheel tag in this tarball is `manylinux_2_28_x86_64`.

The python-build-standalone archive also carries OpenSSL and the other libraries it was built with. Their license texts are in that archive. The upstream note on what is linked is in [Running Distributions](https://github.com/astral-sh/python-build-standalone/blob/20261026/docs/running.rst).

## Not in the default tarball

- Kokoro is an optional engine. It is not installed by `./build-portable.sh`. Its license is the one published with the model and `kokoro-onnx` you choose to install.
- `ffmpeg` is used only for FLAC, Opus, and AAC, and for pitch-preserving speed changes when the `ffmpeg` binary is on `PATH`. Install the distro package if you need those. This tarball does not include `ffmpeg`.
- The optional image in [Dockerfile](Dockerfile) is `python:3.12-slim`. That base image is not part of the tarball.

## Other voices

Piper voices are separate works. The tarball includes `en_US-joe-medium` only. `en_US-ryan-high` is CC BY-NC-SA 4.0 on its [model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ryan/high/MODEL_CARD) and is not included. Read the `MODEL_CARD` beside any other voice before you ship it: https://huggingface.co/rhasspy/piper-voices

## Source

The source for this project is https://github.com/crome1394/local-tts-bookorbit-piper-addon. Upstream source for the GPL components is in the table above. If you redistribute the tarball, keep [LICENSE](LICENSE), [NOTICE](NOTICE), this file, and those upstream links with it.
