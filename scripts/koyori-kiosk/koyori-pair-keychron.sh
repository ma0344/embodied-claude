#!/usr/bin/env bash
# Pair Keychron K4 MAX (or similar) to koyori over Bluetooth.
#
# K4 MAX may advertise a new (random) MAC each scan — we pair by name, not saved MAC.
#
# Usage:
#   ./koyori-pair-keychron.sh       # slot 2 (koyori), auto-detect Keychron from scan
#   ./koyori-pair-keychron.sh 2
#
# Before running: Fn+<slot> long-press ~3s until LED flashes (pairing mode).

set -euo pipefail

SLOT="${1:-2}"
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-Keychron}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma (not root)." >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Install: sudo apt install -y bluez" >&2
  exit 1
fi

echo "=== Keychron K4 MAX → koyori (Bluetooth slot $SLOT) ==="
echo ""
echo "Keyboard (USB unplugged):"
echo "  1. Fn+$SLOT  — select slot $SLOT (dedicate this slot to koyori only)"
echo "  2. Hold Fn+$SLOT ~3s — LED fast blink (pairing mode)"
echo "  3. If not found: Fn+J+Z (Windows/Android), then repeat"
echo ""
echo "Note: MAC may change each time (random address). Pairing uses the name, not MAC."
echo ""
read -r -p "Press Enter when LED is flashing ..."

bluetoothctl power on >/dev/null 2>&1 || true
bluetoothctl agent on >/dev/null 2>&1 || true
bluetoothctl default-agent >/dev/null 2>&1 || true
bluetoothctl scan on >/dev/null 2>&1 || true

echo "Scanning 20s for *${NAME_PATTERN}* ..."
sleep 20
bluetoothctl scan off >/dev/null 2>&1 || true

mapfile -t HITS < <(bluetoothctl devices 2>/dev/null | grep -i "$NAME_PATTERN" || true)

if ((${#HITS[@]} == 0)); then
  echo "No device matching '$NAME_PATTERN'. All devices:"
  bluetoothctl devices
  echo ""
  echo "Try pairing mode again, or set KOYORI_KEYCHRON_NAME='K4 MAX' $0"
  exit 1
fi

echo ""
echo "Found:"
for i in "${!HITS[@]}"; do
  echo "  [$((i + 1))] ${HITS[$i]}"
done

MAC=""
if ((${#HITS[@]} == 1)); then
  MAC=$(awk '{print $2}' <<<"${HITS[0]}")
else
  read -r -p "Pick number [1-${#HITS[@]}]: " pick
  MAC=$(awk '{print $2}' <<<"${HITS[$((pick - 1))]}")
fi

echo "Using $MAC"
bluetoothctl pair "$MAC" || true
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC"

mkdir -p ~/.config
{
  echo "# Keychron slot $SLOT on koyori — MAC may rotate; use koyori-connect-keychron.sh"
  echo "SLOT=$SLOT"
  echo "LAST_MAC=$MAC"
  echo "NAME_PATTERN=$NAME_PATTERN"
  echo "PAIRED_AT=$(date -Is)"
} >~/.config/koyori-keychron

echo ""
bluetoothctl info "$MAC" | head -8
echo ""
echo "Test typing in webui. Reconnect later: Fn+$SLOT or  koyori-connect-keychron.sh"
echo "If it drops after reboot: docs/koyori-input-sharing.md (random MAC section)"
