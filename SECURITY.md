# Security

`local-tts-bookorbit-piper-addon` is a local speech service for BookOrbit.
The text of a book is sensitive. The process is also a CPU consumer on a
small container. The defaults match that.

## What we assume

- The server runs on the same machine as BookOrbit, bound to `127.0.0.1`.
- The person who can write the voices directory and the environment is the administrator.
- Voice models are files the administrator chose to put there.

## What the defaults prevent

- Another host reaching the port. Bind `127.0.0.1` unless you set `BOOKORBIT_TTS_API_KEY`.
- An API that fetches voices or files. Downloads happen only through the `bookorbit-tts download` command, and only for a Piper voice id.
- A huge JSON body, a huge sentence, or an unbounded queue of synthesis jobs.
- Error responses that repeat filesystem paths.
- A sentence passed to espeak-ng being parsed as a command flag.
- A systemd unit written by `install.sh` from a host or port value that contains extra directives.
- The optional container running as root, holding extra capabilities, or publishing the port on every host interface.

## If BookOrbit is on another machine

Set a long random `BOOKORBIT_TTS_API_KEY`, and do not publish the port past the private network those two machines share. The bearer token is the only application-level check. Put TLS in front of it if the path crosses a network you do not trust. `/health` stays unauthenticated so a local probe can run; it reports the engine name, voice count, and uptime, not the text you synthesized.

## Reporting

Open an issue at <https://github.com/crome1394/local-tts-bookorbit-piper-addon/issues>
with the version from `bookorbit-tts --version` and what you observed. Leave out API keys and book text.
