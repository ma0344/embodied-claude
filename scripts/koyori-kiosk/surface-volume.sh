#!/bin/bash
# Hardware volume keys → PipeWire/Pulse (user session) + kiosk overlay notify.
set -euo pipefail

USER="${KOYORI_AUDIO_USER:-ma}"
UID_NUM=$(id -u "$USER")
export XDG_RUNTIME_DIR="/run/user/${UID_NUM}"
STEP="${KOYORI_VOLUME_STEP:-5%}"
NOTIFY_URL="${KOYORI_AUDIO_NOTIFY_URL:-http://127.0.0.1:18791/volume-notify}"

case "${1:-}" in
  up) DELTA="+" ;;
  down) DELTA="-" ;;
  *) exit 0 ;;
esac

run_wpctl() {
  sudo -u "$USER" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    wpctl set-volume @DEFAULT_AUDIO_SINK@ "${STEP}${DELTA}"
}

run_pactl() {
  sudo -u "$USER" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    pactl set-sink-volume @DEFAULT_SINK@ "${DELTA}${STEP}"
}

if command -v wpctl >/dev/null 2>&1; then
  run_wpctl
elif command -v pactl >/dev/null 2>&1; then
  run_pactl
else
  amixer -q sset Master "${STEP}${DELTA}"
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsS -X POST "$NOTIFY_URL" >/dev/null 2>&1 || true
fi
