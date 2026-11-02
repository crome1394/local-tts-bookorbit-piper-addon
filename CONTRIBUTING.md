# Contributing

Thanks for taking a look. Issues and pull requests are welcome.

## Before you open an issue

- Check the troubleshooting table in [README.md](README.md).
- Include your OS, Python version, engine (`piper`, `kokoro`, or `espeak`), and
  the output of:

  ```bash
  bookorbit-tts doctor
  ```

- If BookOrbit cannot connect, include the exact base URL and the output of:

  ```bash
  curl -i http://127.0.0.1:8765/v1/models
  ```

## Development setup

```bash
git clone https://github.com/crome1394/local-tts-bookorbit-piper-addon.git
cd local-tts-bookorbit-piper-addon
python3 -m venv .venv
.venv/bin/pip install -e '.[kokoro,test]'
.venv/bin/python -m pytest
```

The fast API tests use `espeak-ng`; install it if your distribution does not
ship it.

## Pull requests

- Keep the default path small: one ONNX thread, one concurrent request, no GPU
  requirement.
- Add or update tests for behavior changes.
- Run `pytest` and `bash -n install.sh run.sh build-portable.sh` before opening
  the PR.
- Do not commit voice models, model caches, generated tarballs, or virtualenvs.

## License

By contributing, you agree that your contribution is licensed under
GPL-3.0-or-later, the same license as the project.
