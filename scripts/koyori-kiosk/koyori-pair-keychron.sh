#!/usr/bin/env bash
# Pair Keychron K4 MAX to koyori. One bluetoothctl session for scan + pair.
#
# Usage: ./koyori-pair-keychron.sh [slot]

set -euo pipefail

SLOT="${1:-2}"
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"
SCAN_SEC="${KOYORI_BT_SCAN_SEC:-30}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma (not root)." >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Install: sudo apt install -y bluez" >&2
  exit 1
fi

if command -v rfkill >/dev/null 2>&1 && rfkill list bluetooth 2>/dev/null | grep -q 'Soft blocked: yes'; then
  echo "Bluetooth is soft-blocked. Try: sudo rfkill unblock bluetooth" >&2
  exit 1
fi

koyori_bt_find_mac() {
  local pattern="$1"
  local log="$2"
  local mac=""

  mac=$(grep -iE '\[(NEW|CHG)\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | tail -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }

  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }

  return 1
}

echo "=== Keychron K4 MAX → koyori (slot $SLOT) ==="
echo ""
echo "Keyboard: USB unplugged, Fn+$SLOT, hold Fn+$SLOT ~3s (LED blink)"
echo "Pattern: *${NAME_PATTERN}*  |  scan: ${SCAN_SEC}s"
echo ""
read -r -p "Press Enter when LED is flashing ..."

SCAN_LOG=$(mktemp)
trap 'rm -f "$SCAN_LOG"' EXIT

echo "Scanning ${SCAN_SEC}s (single bluetoothctl session) ..."
{
  echo "power on"
  echo "agent NoInputNoOutput"
  echo "default-agent"
  echo "scan on"
  sleep "$SCAN_SEC"
  echo "devices"
  echo "scan off"
  echo "quit"
} | bluetoothctl 2>&1 | tee "$SCAN_LOG" || true

MAC=""
if ! MAC=$(koyori_bt_find_mac "$NAME_PATTERN" "$SCAN_LOG"); then
  echo ""
  echo "No device matching '$NAME_PATTERN'."
  echo ""
  echo "Bluetooth adapter:"
  bluetoothctl show 2>/dev/null | head -6 || true
  echo ""
  echo "All devices in scan log:"
  grep -iE '\[(NEW|CHG)\] Device|^Device [0-9A-F]' "$SCAN_LOG" \
    | grep -vi 'Controller' | tail -25 || echo "  (empty — keyboard not advertising?)"
  echo ""
  echo "Retry: pairing mode +  KOYORI_KEYCHRON_NAME='Keychron' $0 $SLOT"
  exit 1
fi

echo ""
echo "Found $MAC — pairing ..."
PAIR_LOG=$(mktemp)
trap 'rm -f "$SCAN_LOG" "$PAIR_LOG"' EXIT

{
  echo "power on"
  echo "agent NoInputNoOutput"
  echo "default-agent"
  echo "pair $MAC"
  echo "trust $MAC"
  echo "connect $MAC"
  echo "quit"
} | bluetoothctl 2>&1 | tee "$PAIR_LOG" || true

mkdir -p ~/.config
{
  echo "SLOT=$SLOT"
  echo "LAST_MAC=$MAC"
  echo "NAME_PATTERN=$NAME_PATTERN"
  echo "PAIRED_AT=$(date -Is)"
} >~/.config/koyori-keychron

echo ""
bluetoothctl info "$MAC" 2>/dev/null | head -12 || true
echo ""
if grep -qi 'Connected: yes' "$PAIR_LOG" || bluetoothctl info "$MAC" 2>/dev/null | grep -q 'Connected: yes'; then
  echo "OK — connected. Test in webui; 半/全 for Japanese."
else
  echo "Pair finished — if not connected, run: koyori-connect-keychron.sh"
fi
