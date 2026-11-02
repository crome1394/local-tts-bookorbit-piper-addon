#!/bin/sh
# First run inside a container: fetch the default voice if none is present.
set -e

if [ -z "$(ls -A "${BOOKORBIT_TTS_DATA_DIR:-/data}/voices" 2>/dev/null)" ]; then
  echo "No voices found, downloading ${BOOKORBIT_TTS_VOICE:-en_US-joe-medium}..."
  bookorbit-tts download "${BOOKORBIT_TTS_VOICE:-en_US-joe-medium}"
fi

exec "$@"
