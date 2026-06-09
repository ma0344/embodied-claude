#!/usr/bin/env bash
# Pair Keychron K2 (or similar) to koyori over Bluetooth.
#
# Usage:
#   ./koyori-pair-keychron.sh              # interactive
#   ./koyori-pair-keychron.sh 2            # use K2 slot 2 (Fn+2) — default for koyori
#
# Before running: on the keyboard, hold Fn+<slot> ~3s until LED flashes (pairing mode).

set -euo pipefail

SLOT="${1:-2}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma (not root). Use: sudo apt install bluez && ./koyori-pair-keychron.sh" >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Install bluez first: sudo apt install -y bluez" >&2
  exit 1
fi

echo "=== Keychron K2 → koyori (slot $SLOT) ==="
echo ""
echo "On the keyboard:"
echo "  1. Switch to Bluetooth slot $SLOT  (Fn+$SLOT)"
echo "  2. Hold Fn+$SLOT ~3 seconds until LED flashes fast (pairing mode)"
echo "  3. If koyori never sees it: try Fn+J+Z (Windows/Android mode)"
echo ""
read -r -p "Press Enter when the keyboard LED is flashing ..."

bluetoothctl <<EOF
power on
agent on
default-agent
scan on
EOF

echo ""
echo "Scanning 15 seconds — look for Keychron ..."
sleep 15

bluetoothctl devices | grep -i keychron || bluetoothctl devices

echo ""
read -r -p "Paste device MAC (AA:BB:CC:DD:EE:FF): " MAC
MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')

if [[ ! "$MAC" =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]]; then
  echo "Invalid MAC: $MAC" >&2
  exit 1
fi

bluetoothctl <<EOF
scan off
pair $MAC
trust $MAC
connect $MAC
EOF

echo ""
echo "Done. Test typing in a text field."
echo "Reconnect later: Fn+$SLOT on the keyboard, or:"
echo "  bluetoothctl connect $MAC"
echo ""
echo "Save MAC for reference:"
echo "  echo '$MAC' >> ~/.config/koyori-keychron-mac"
