#!/usr/bin/env bash
# Capture one JPEG from Surface Go front camera (libcamera via GStreamer).
#
# Requires on koyori:
#   linux-surface kernel, libcamera-ipa, gstreamer1.0-libcamera,
#   gstreamer1.0-plugins-good, gstreamer1.0-tools
#   BIOS: front camera ON, rear/IR OFF
#
# Usage:
#   ./scripts/koyori-capture.sh [/path/to/out.jpg]
#   KOYORI_CAPTURE_TIMEOUT=10 ./scripts/koyori-capture.sh
#
# Do not use cam+ffmpeg raw dump on IPU3; IPA processing needs GStreamer.
# Architecture / ma-home integration: docs/ops/koyori-near-eye.md

set -euo pipefail

OUT="${1:-/tmp/koyori.jpg}"
TIMEOUT_SEC="${KOYORI_CAPTURE_TIMEOUT:-8}"
# Skip early warmup frames (Zero sequence / exposure settle).
PICK_INDEX="${KOYORI_PICK_FRAME:-4}"
CAMERA_NAME="${KOYORI_CAMERA_NAME:-\\\_SB_.PCI0.LNK1}"

WORKDIR=$(mktemp -d)
LOG="$WORKDIR/gst.log"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

run_capture() {
  local use_name="${1:-0}"
  : >"$LOG"

  if [[ "$use_name" == "1" ]]; then
    timeout "$TIMEOUT_SEC" gst-launch-1.0 -e \
      libcamerasrc camera-name="$CAMERA_NAME" ! \
      'video/x-raw,format=NV12,width=1280,height=720,framerate=30/1' ! \
      queue max-size-buffers=2 leaky=downstream ! \
      videoconvert ! jpegenc quality=85 ! \
      multifilesink location="$WORKDIR/f-%05d.jpg" sync=false \
      >>"$LOG" 2>&1 || true
  else
    timeout "$TIMEOUT_SEC" gst-launch-1.0 -e \
      libcamerasrc ! \
      'video/x-raw,format=NV12,width=1280,height=720,framerate=30/1' ! \
      queue max-size-buffers=2 leaky=downstream ! \
      videoconvert ! jpegenc quality=85 ! \
      multifilesink location="$WORKDIR/f-%05d.jpg" sync=false \
      >>"$LOG" 2>&1 || true
  fi
}

run_capture 1
mapfile -t FRAMES < <(compgen -G "$WORKDIR/f-*.jpg" | sort)

if ((${#FRAMES[@]} == 0)); then
  run_capture 0
  mapfile -t FRAMES < <(compgen -G "$WORKDIR/f-*.jpg" | sort)
fi

if ((${#FRAMES[@]} == 0)); then
  echo "koyori-capture: no JPEG produced (timeout=${TIMEOUT_SEC}s)" >&2
  echo "--- gst-launch log ---" >&2
  cat "$LOG" >&2
  exit 1
fi

idx=$PICK_INDEX
if ((idx >= ${#FRAMES[@]})); then
  idx=$((${#FRAMES[@]} - 1))
fi

cp "${FRAMES[$idx]}" "$OUT"
bytes=$(wc -c <"$OUT" | tr -d ' ')
if ((bytes < 500)); then
  echo "koyori-capture: output too small (${bytes} bytes): $OUT" >&2
  cat "$LOG" >&2
  exit 1
fi

echo "$OUT"
