# Security

This is a local speech service for [BookOrbit](https://bookorbit.app). The text of a book is sensitive, and synthesis spends CPU. The defaults assume the server is on the same machine as BookOrbit.

## Assumptions

- `./run.sh` binds `127.0.0.1`. `bookorbit-tts serve` does the same unless `BOOKORBIT_TTS_HOST` is set.
- The administrator is whoever can write the voice directories and the process environment.
- Voice files are whatever that person put in `voices/` or `data/voices`. The HTTP API does not fetch them.

## What the process actually does

- A bind address other than `127.0.0.1`, `localhost`, or `::1`, with no `BOOKORBIT_TTS_API_KEY`, logs a warning and still serves. The key is compared as SHA-256 digests. `/v1/audio/speech`, `/v1/audio/voices`, `/v1/models`, and `/dev/captioned_speech` require it when it is set. `/health` does not.
- `bookorbit-tts download` accepts a Piper voice id of the form `en_US-joe-medium`. A client voice id has to match a short token pattern, and then has to be a voice the process already loaded.
- The JSON body size is derived from the text limit. Text defaults to 4000 characters and cannot be set above 20000. A full synthesis queue returns `429` with `Retry-After: 2`.
- An unexpected synthesis error is logged, including any path in the traceback. The HTTP client gets `synthesis failed`. A bad request, such as an unknown voice id, is a `400` and names the voice id, not a filesystem path.
- When the espeak engine is the one selected, the sentence is passed after `--`, so a line that starts with a dash is not read as a flag.
- `install.sh` accepts a host and a port only when they match a narrow pattern, and a Piper voice id only when it matches the `en_US-joe-medium` shape. It refuses an install path that contains a quote or a newline. The host and port are written into the systemd unit. The voice id is only used as a download name.
- [docker-compose.example.yml](docker-compose.example.yml) runs as uid 10001, drops all capabilities, sets `no-new-privileges`, limits the container to 1 CPU and 1 GB, and publishes `127.0.0.1:8765:8765`. Inside the container the process binds `0.0.0.0` so that published port can connect. The host mapping is what keeps it off other interfaces.
- `/docs` and `/openapi.json` are absent unless `BOOKORBIT_TTS_DOCS=1`.

`/health` returns status, version, uptime, engine name, the default voice id, the voice count, and the concurrency setting. It does not return synthesized text.

## Another machine

Set a long random `BOOKORBIT_TTS_API_KEY`. Keep the port on the private network those two machines share. The bearer token is the only check this application makes. Put TLS in front of it if the path crosses a network you do not trust.

## Reporting

Open an issue at <https://github.com/crome1394/local-tts-bookorbit-piper-addon/issues> with the output of `bookorbit-tts --version` and what you saw. Leave out API keys and book text.
