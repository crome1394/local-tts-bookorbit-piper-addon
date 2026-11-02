#!/usr/bin/env bash
# Run bookorbit-tts from this directory, without installing anything system-wide.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$ROOT/.venv/bin/bookorbit-tts"

if [[ ! -x "$BINARY" ]]; then
  echo "bookorbit-tts is not installed in $ROOT." >&2
  echo "Run ./install.sh --local first." >&2
  exit 1
fi

# Defaults tuned for a small container shared with BookOrbit. Override any of
# these in the environment, or pass the matching flag after ./run.sh.
export BOOKORBIT_TTS_HOST="${BOOKORBIT_TTS_HOST:-127.0.0.1}"
export BOOKORBIT_TTS_PORT="${BOOKORBIT_TTS_PORT:-8765}"
export BOOKORBIT_TTS_ENGINE="${BOOKORBIT_TTS_ENGINE:-piper}"
export BOOKORBIT_TTS_THREADS="${BOOKORBIT_TTS_THREADS:-1}"
export BOOKORBIT_TTS_CONCURRENCY="${BOOKORBIT_TTS_CONCURRENCY:-1}"
# Drop Hugging Face piper-voices checkouts here. Nested folders are fine.
export BOOKORBIT_TTS_VOICES_DIR="${BOOKORBIT_TTS_VOICES_DIR:-$ROOT/voices}"
mkdir -p "$BOOKORBIT_TTS_VOICES_DIR"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"

# A --local install keeps voices in ./data; otherwise fall back to the normal
# per-user data directory.
if [[ -z "${BOOKORBIT_TTS_DATA_DIR:-}" && -d "$ROOT/data/voices" ]]; then
  export BOOKORBIT_TTS_DATA_DIR="$ROOT/data"
fi

# Share the container politely with BookOrbit.
NICE=()
if command -v nice >/dev/null 2>&1 && nice -n 5 true 2>/dev/null; then
  NICE=(nice -n 5)
fi

exec "${NICE[@]}" "$BINARY" serve "$@"
