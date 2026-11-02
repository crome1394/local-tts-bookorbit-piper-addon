#!/usr/bin/env bash
# Install bookorbit-tts into a local virtualenv.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"
VOICE="en_US-joe-medium"
FULL=0
SERVICE=0
SYSTEM_SERVICE=0
NO_INSTALL=0
LOCAL_DATA=0
PORT=8765
HOST="127.0.0.1"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --full             also install Kokoro (better voice, ~140 MB extra)
  --local            keep voices/models in ./data (self-contained install)
  --voice ID         Piper voice to download (repeat with --voice-extra)
  --voice-extra ID   download an additional Piper voice
  --service          install and start a systemd *user* service
  --system-service   install and start a systemd *system* service (needs root)
  --no-install       only (re)write/start the service; skip pip and downloads
  --port N           service port (default 8765)
  --host ADDR        bind address (default 127.0.0.1)
  -h, --help         show this help

For a minimal, no-Docker LXC:
  ./install.sh --local     # everything stays in this directory
  ./run.sh                 # start it in the foreground

The default voice is en_US-joe-medium (CC0). Use --voice to change it.

Examples:
  ./install.sh
  ./install.sh --local
  ./install.sh --full --local --service
  ./install.sh --voice en_US-kristin-medium
  sudo ./install.sh --system-service --no-install
EOF
}

EXTRA_VOICES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --full) FULL=1 ;;
    --local) LOCAL_DATA=1 ;;
    --service) SERVICE=1 ;;
    --system-service) SYSTEM_SERVICE=1 ;;
    --no-install) NO_INSTALL=1 ;;
    --voice) VOICE="$2"; shift ;;
    --voice-extra) EXTRA_VOICES+=("$2"); shift ;;
    --port) PORT="$2"; shift ;;
    --host) HOST="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( 10#$PORT < 1 || 10#$PORT > 65535 )); then
  echo "Invalid port: $PORT" >&2
  exit 1
fi
if ! [[ "$HOST" =~ ^[A-Za-z0-9:.][A-Za-z0-9.:_-]{0,252}$ ]]; then
  echo "Invalid host: $HOST" >&2
  echo "Use an address such as 127.0.0.1 or 0.0.0.0." >&2
  exit 1
fi
voice_ok='^[a-z]{2,3}_[A-Za-z]{2,8}-[A-Za-z0-9_]{1,48}-(x_low|low|medium|high)$'
if ! [[ "$VOICE" =~ $voice_ok ]]; then
  echo "Invalid Piper voice id: $VOICE" >&2
  exit 1
fi
for extra in "${EXTRA_VOICES[@]}"; do
  if ! [[ "$extra" =~ $voice_ok ]]; then
    echo "Invalid Piper voice id: $extra" >&2
    exit 1
  fi
done
if [[ "$ROOT" == *$'\n'* || "$ROOT" == *'"'* ]]; then
  echo "Install path must not contain quotes or newlines." >&2
  exit 1
fi

if [[ "$SERVICE" == "1" && "$SYSTEM_SERVICE" == "1" ]]; then
  echo "Use either --service or --system-service, not both." >&2
  exit 1
fi

DATA_ENV=""
if [[ "$LOCAL_DATA" == "1" ]]; then
  export BOOKORBIT_TTS_DATA_DIR="$ROOT/data"
  DATA_ENV="Environment=\"BOOKORBIT_TTS_DATA_DIR=$ROOT/data\""
fi

if [[ "$NO_INSTALL" == "0" ]]; then
  command -v "$PYTHON" >/dev/null || { echo "python3 not found" >&2; exit 1; }
  "$PYTHON" - <<'PY' || { echo "Python 3.10 or newer is required" >&2; exit 1; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

  echo "==> Creating virtualenv in $VENV"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --no-cache-dir --upgrade pip

  if [[ "$FULL" == "1" ]]; then
    echo "==> Installing bookorbit-tts with Kokoro support"
    "$VENV/bin/pip" install --quiet --no-cache-dir -e "$ROOT[kokoro]"
  else
    echo "==> Installing bookorbit-tts (Piper only)"
    "$VENV/bin/pip" install --quiet --no-cache-dir -e "$ROOT"
  fi

  echo "==> Downloading Piper voice $VOICE"
  "$VENV/bin/bookorbit-tts" download "$VOICE" "${EXTRA_VOICES[@]}"

  if [[ "$FULL" == "1" ]]; then
    echo "==> Downloading Kokoro model (~140 MB)"
    "$VENV/bin/bookorbit-tts" download "$VOICE" --kokoro >/dev/null
  fi

  echo "==> Checking the installation"
  "$VENV/bin/bookorbit-tts" doctor
else
  [[ -x "$VENV/bin/bookorbit-tts" ]] || {
    echo "$VENV/bin/bookorbit-tts is missing; run the installer without --no-install first." >&2
    exit 1
  }
fi

write_unit() {
  local target="$1" wanted_by="$2" user_line="$3"
  cat >"$target" <<EOF
[Unit]
Description=BookOrbit local text-to-speech
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
${user_line}WorkingDirectory=$ROOT
Environment="BOOKORBIT_TTS_HOST=$HOST"
Environment="BOOKORBIT_TTS_PORT=$PORT"
Environment="BOOKORBIT_TTS_ENGINE=piper"
${DATA_ENV}
Environment="BOOKORBIT_TTS_THREADS=1"
Environment="BOOKORBIT_TTS_CONCURRENCY=1"
Environment="OMP_NUM_THREADS=1"
Environment="OPENBLAS_NUM_THREADS=1"
Nice=5
ExecStart=$VENV/bin/bookorbit-tts serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=$wanted_by
EOF
}

wait_for_health() {
  command -v curl >/dev/null || return 0
  for _ in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
      echo "==> Health check passed on port $PORT"
      return 0
    fi
    sleep 0.5
  done
  echo "==> Warning: the service has not answered on port $PORT yet; check its logs." >&2
}

if [[ "$SERVICE" == "1" ]]; then
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  mkdir -p "$UNIT_DIR"
  write_unit "$UNIT_DIR/local-tts-bookorbit-piper-addon.service" "default.target" ""
  systemctl --user daemon-reload
  systemctl --user enable --now local-tts-bookorbit-piper-addon.service
  wait_for_health
  echo "==> Service started: systemctl --user status local-tts-bookorbit-piper-addon"
  echo "    To start it at boot without logging in: loginctl enable-linger $USER"
fi

if [[ "$SYSTEM_SERVICE" == "1" ]]; then
  [[ "$EUID" -eq 0 ]] || { echo "--system-service needs root (use sudo)." >&2; exit 1; }
  RUN_USER="${SUDO_USER:-$(id -un)}"
  write_unit "/etc/systemd/system/local-tts-bookorbit-piper-addon.service" "multi-user.target" "User=$RUN_USER"$'\n'
  systemctl daemon-reload
  systemctl enable --now local-tts-bookorbit-piper-addon.service
  wait_for_health
  echo "==> System service started as $RUN_USER: systemctl status local-tts-bookorbit-piper-addon"
fi

if [[ "$HOST" == "127.0.0.1" || "$HOST" == "localhost" || "$HOST" == "::1" ]]; then
  BASE_URL="http://127.0.0.1:$PORT/v1"
else
  BASE_URL="http://<this-machine>:$PORT/v1"
fi

if [[ "$LOCAL_DATA" == "1" ]]; then
  RUN_HINT="$ROOT/run.sh"
else
  RUN_HINT="$VENV/bin/bookorbit-tts serve"
fi

cat <<EOF

Done.

BookOrbit settings (Settings -> Admin -> Text to Speech):
  Name       Local TTS
  Base URL   $BASE_URL
  Model      tts-1
  API key    leave empty
  Voice discovery: on

Start it manually with: $RUN_HINT
EOF
if [[ "$HOST" == "0.0.0.0" ]]; then
  echo "The server is reachable from other machines because it binds $HOST."
else
  echo "The server is bound to $HOST (local only)."
fi
