#!/usr/bin/env bash
# Build a self-contained Linux x86_64 tarball: Python, dependencies, server and
# the default Piper voice all live inside one directory. No Docker, no system
# Python, no pip on the target.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$("$ROOT/.venv/bin/python" -c 'import bookorbit_tts; print(bookorbit_tts.__version__)' 2>/dev/null \
  || python3 -c 'import sys; sys.path.insert(0, "'"$ROOT"'/src"); import bookorbit_tts; print(bookorbit_tts.__version__)')"

# Known-good python-build-standalone release. Override for a newer build.
PBS_TAG="${PBS_TAG:-20261026}"
PY_VERSION="${PY_VERSION:-3.12.16}"
VOICE="${VOICE:-en_US-joe-medium}"
if ! [[ "$VOICE" =~ ^[a-z]{2,3}_[A-Za-z]{2,8}-[A-Za-z0-9_]{1,48}-(x_low|low|medium|high)$ ]]; then
  echo "Invalid Piper voice id: $VOICE" >&2
  exit 1
fi
ARCH="${ARCH:-x86_64}"
NAME="local-tts-bookorbit-piper-addon"
DIST="$ROOT/dist"
BUNDLE="$DIST/$NAME"
CACHE="$ROOT/.build"
ASSET="cpython-${PY_VERSION}+${PBS_TAG}-${ARCH}-unknown-linux-gnu-install_only_stripped.tar.gz"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${ASSET}"

mkdir -p "$CACHE" "$DIST"
if [[ ! -f "$CACHE/$ASSET" ]]; then
  echo "==> Downloading bundled Python ($ASSET)"
  curl -fL --retry 3 -o "$CACHE/$ASSET" "$URL"
fi

echo "==> Unpacking Python into $BUNDLE"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE"
tar -xzf "$CACHE/$ASSET" -C "$BUNDLE"

echo "==> Installing $NAME $VERSION and dependencies"
"$BUNDLE/python/bin/python3" -m pip install --quiet --no-cache-dir --upgrade pip
"$BUNDLE/python/bin/python3" -m pip install --quiet --no-cache-dir "$ROOT"

echo "==> Downloading Piper voice $VOICE"
BOOKORBIT_TTS_DATA_DIR="$BUNDLE/data" \
  "$BUNDLE/python/bin/bookorbit-tts" download "$VOICE"

echo "==> Copying license and project documents"
cp "$ROOT/LICENSE" "$ROOT/NOTICE" "$ROOT/THIRD_PARTY_NOTICES.md" "$BUNDLE/"

cat >"$BUNDLE/run.sh" <<'EOF'
#!/usr/bin/env bash
# Self-contained launcher. Override any variable before calling this script.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BOOKORBIT_TTS_DATA_DIR="${BOOKORBIT_TTS_DATA_DIR:-$ROOT/data}"
export BOOKORBIT_TTS_VOICES_DIR="${BOOKORBIT_TTS_VOICES_DIR:-$ROOT/voices}"
mkdir -p "$BOOKORBIT_TTS_VOICES_DIR"
export BOOKORBIT_TTS_HOST="${BOOKORBIT_TTS_HOST:-127.0.0.1}"
export BOOKORBIT_TTS_PORT="${BOOKORBIT_TTS_PORT:-8765}"
export BOOKORBIT_TTS_ENGINE="${BOOKORBIT_TTS_ENGINE:-piper}"
export BOOKORBIT_TTS_THREADS="${BOOKORBIT_TTS_THREADS:-1}"
export BOOKORBIT_TTS_CONCURRENCY="${BOOKORBIT_TTS_CONCURRENCY:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
NICE=()
if command -v nice >/dev/null 2>&1 && nice -n 5 true 2>/dev/null; then
  NICE=(nice -n 5)
fi
exec "${NICE[@]}" "$ROOT/python/bin/python3" -m bookorbit_tts serve "$@"
EOF
chmod +x "$BUNDLE/run.sh"

cat >"$BUNDLE/README.txt" <<EOF
$NAME $VERSION portable bundle
================================================

Extract this directory anywhere writable, then run:

    ./run.sh

It listens on http://127.0.0.1:8765 by default. Set BOOKORBIT_TTS_HOST=0.0.0.0
to accept connections from other machines, and BOOKORBIT_TTS_PORT to change
the port.

BookOrbit provider settings (same LXC):
    Base URL   http://127.0.0.1:8765/v1
    Model      tts-1
    API key    leave empty
    Voice discovery: on

Everything is inside this directory: Python, dependencies, voice model and the
server itself. Remove the directory to uninstall. No Docker, no system Python,
no pip, no systemd unit.

This build is for Linux x86_64 with glibc 2.28 or newer (Debian 10+, Ubuntu
20.04+, Proxmox Debian 12). It includes Piper only; mp3 output and wav/pcm are
built in. For flac/opus/aac output, install ffmpeg on the LXC (BookOrbit uses
mp3 by default, so this is optional).

Bundled voice: $VOICE (CC0). Other voices have their own licenses; see
THIRD_PARTY_NOTICES.md before redistributing them.

Extra Piper voices go in the voices/ directory. A folder from
https://huggingface.co/rhasspy/piper-voices can be copied in as-is.
Restart after adding one.

License: GPL-3.0-or-later. See LICENSE and NOTICE.

Project home:
https://github.com/crome1394/local-tts-bookorbit-piper-addon
EOF

echo "==> Testing the bundle"
BOOKORBIT_TTS_PORT=8799 "$BUNDLE/run.sh" >"$CACHE/portable-test.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8799/health >/dev/null 2>&1; then break; fi
  sleep 0.25
done
curl -sf http://127.0.0.1:8799/health >/dev/null || {
  echo "Bundle did not start; see $CACHE/portable-test.log" >&2
  tail -30 "$CACHE/portable-test.log" >&2
  exit 1
}
curl -sf -X POST http://127.0.0.1:8799/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d "{\"input\":\"Portable bundle test.\",\"voice\":\"$VOICE\",\"response_format\":\"mp3\"}" \
  -o "$CACHE/portable-test.mp3"
[[ -s "$CACHE/portable-test.mp3" ]] || { echo "Bundle produced no audio" >&2; exit 1; }
kill $PID 2>/dev/null || true
wait $PID 2>/dev/null || true
trap - EXIT
echo "    OK: health and mp3 synthesis"

TARBALL="$DIST/${NAME}-linux-${ARCH}.tar.gz"
echo "==> Creating $TARBALL"
tar -C "$DIST" -czf "$TARBALL" "$NAME"
ls -lh "$TARBALL"
sha256sum "$TARBALL"
echo
echo "Publish it as the release asset named: $(basename "$TARBALL")"
echo "On the target machine:"
echo "  tar -xzf $(basename "$TARBALL")"
echo "  cd $NAME && ./run.sh"
