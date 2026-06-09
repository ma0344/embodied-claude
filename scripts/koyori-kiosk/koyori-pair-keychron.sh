#!/usr/bin/env bash
# Pair Keychron K4 MAX (or similar) to koyori over Bluetooth.
#
# Usage:
#   ./koyori-pair-keychron.sh       # slot 2 (koyori)
#   ./koyori-pair-keychron.sh 2
#
# Before running: Fn+<slot> long-press ~3s until LED flashes (pairing mode).

set -euo pipefail

SLOT="${1:-2}"
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma (not root)." >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Install: sudo apt install -y bluez" >&2
  exit 1
fi

koyori_bt_find_mac() {
  local pattern="$1"
  local log="$2"
  local mac=""

  # [NEW] Device AA:BB:... Keychron K4 Max
  mac=$(grep -iE '^\[(NEW|CHG)\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | tail -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }

  # Device AA:BB:... Keychron K4 Max  (devices command)
  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }

  return 1
}

echo "=== Keychron K4 MAX → koyori (Bluetooth slot $SLOT) ==="
echo ""
echo "Keyboard (USB unplugged):"
echo "  1. Fn+$SLOT  — koyori-dedicated slot"
echo "  2. Hold Fn+$SLOT ~3s — LED fast blink (pairing mode)"
echo "  3. If not found: Fn+J+Z (Windows/Android), then repeat"
echo ""
echo "Looking for name matching: *${NAME_PATTERN}*"
echo "(MAC may be random — we parse the scan log, not a saved address)"
echo ""
read -r -p "Press Enter when LED is flashing ..."

SCAN_LOG=$(mktemp)
trap 'rm -f "$SCAN_LOG"' EXIT

bluetoothctl power on 2>&1 | tee -a "$SCAN_LOG" || true
bluetoothctl agent on 2>&1 | tee -a "$SCAN_LOG" || true
bluetoothctl default-agent 2>&1 | tee -a "$SCAN_LOG" || true

echo "Scanning 30s (watch for Keychron K4 Max) ..."
if bluetoothctl --help 2>&1 | grep -q -- '--timeout'; then
  bluetoothctl --timeout 30 scan on 2>&1 | tee -a "$SCAN_LOG" || true
else
  timeout 30 bluetoothctl scan on 2>&1 | tee -a "$SCAN_LOG" || true
  bluetoothctl scan off 2>&1 | tee -a "$SCAN_LOG" || true
fi

bluetoothctl devices 2>&1 | tee -a "$SCAN_LOG" || true

MAC=""
if MAC=$(koyori_bt_find_mac "$NAME_PATTERN" "$SCAN_LOG"); then
  echo "Found: $MAC"
else
  echo "No device matching '$NAME_PATTERN' in scan log."
  echo ""
  echo "Devices seen during scan:"
  grep -iE '^\[(NEW|CHG)\] Device|^Device ' "$SCAN_LOG" | grep -vi '^Device Controller' | tail -20 || true
  echo ""
  echo "Try:"
  echo "  KOYORI_KEYCHRON_NAME='Keychron' $0 $SLOT"
  echo "  KOYORI_KEYCHRON_NAME='K4' $0 $SLOT"
  exit 1
fi

echo "Pairing $MAC ..."
if ! bluetoothctl pair "$MAC" 2>&1 | tee -a "$SCAN_LOG"; then
  echo "WARN: pair returned error (may already be paired)"
fi
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC"

mkdir -p ~/.config
{
  echo "# Keychron slot $SLOT — MAC may rotate; reconnect: koyori-connect-keychron.sh"
  echo "SLOT=$SLOT"
  echo "LAST_MAC=$MAC"
  echo "NAME_PATTERN=$NAME_PATTERN"
  echo "PAIRED_AT=$(date -Is)"
} >~/.config/koyori-keychron

echo ""
bluetoothctl info "$MAC" | head -10
echo ""
echo "Test typing in webui. Reconnect: Fn+$SLOT or koyori-connect-keychron.sh"
