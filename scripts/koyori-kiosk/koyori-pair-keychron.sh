#!/usr/bin/env bash
# Pair Keychron K4 MAX to koyori — one bluetoothctl session, wait for pair to finish.
#
# Usage: ./koyori-pair-keychron.sh [slot]

set -euo pipefail

SLOT="${1:-2}"
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"
SCAN_SEC="${KOYORI_BT_SCAN_SEC:-25}"
PAIR_WAIT="${KOYORI_BT_PAIR_WAIT:-20}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma (not root)." >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Install: sudo apt install -y bluez" >&2
  exit 1
fi

# Pick first [NEW] match this scan (active advertiser), not stale cache entries.
koyori_bt_pick_mac() {
  local pattern="$1"
  local log="$2"
  local mac=""
  mac=$(grep -iE '\[NEW\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | head -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | head -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | head -1 \
    | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  return 1
}

echo "=== Keychron K4 MAX → koyori (slot $SLOT) ==="
echo ""
echo "Keyboard: USB unplugged, Fn+$SLOT, hold Fn+$SLOT ~3s (LED blink)"
echo "Pattern: *${NAME_PATTERN}*"
echo ""
read -r -p "Press Enter when LED is flashing ..."

# Drop stale Keychron ghosts (random MAC accumulates).
if [[ -x /usr/local/bin/koyori-bluetooth-cleanup-keychron ]]; then
  sudo koyori-bluetooth-cleanup-keychron 2>/dev/null || true
else
  while read -r _ mac _rest; do
    [[ -n "$mac" ]] && bluetoothctl remove "$mac" 2>/dev/null || true
  done < <(bluetoothctl devices 2>/dev/null | grep -i keychron || true)
fi

LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT

echo "Scan + pair in one session (${SCAN_SEC}s scan, then pair) ..."
{
  echo "power on"
  sleep 1
  echo "agent on"
  echo "default-agent"
  echo "scan on"
  sleep "$SCAN_SEC"
  echo "scan off"
  sleep 1
  echo "devices"
} | bluetoothctl 2>&1 | tee "$LOG" || true

MAC=""
if ! MAC=$(koyori_bt_pick_mac "$NAME_PATTERN" "$LOG"); then
  echo "No *${NAME_PATTERN}* in scan."
  grep -iE '\[NEW\] Device|^Device [0-9A-F]' "$LOG" | grep -i keychron || true
  exit 1
fi

echo ""
echo "Using $MAC (first [NEW] this scan). Pairing — keep keyboard in pairing mode ..."
PAIR_LOG=$(mktemp)
trap 'rm -f "$LOG" "$PAIR_LOG"' EXIT

{
  echo "power on"
  sleep 1
  echo "agent on"
  echo "default-agent"
  echo "pair $MAC"
  sleep "$PAIR_WAIT"
  echo "trust $MAC"
  echo "connect $MAC"
  sleep 8
  echo "info $MAC"
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
if grep -qiE 'Pairing successful|Connection successful|Paired: yes' "$PAIR_LOG"; then
  echo "OK — paired/connected."
elif bluetoothctl info "$MAC" 2>/dev/null | grep -q 'Paired: yes'; then
  echo "OK — paired."
else
  echo "Pair may have failed. Log tail:"
  tail -15 "$PAIR_LOG"
  echo ""
  echo "Retry: keep Fn+$SLOT blinking, run again, or:"
  echo "  bluetoothctl"
  echo "  agent on"
  echo "  default-agent"
  echo "  pair $MAC"
  echo "  (wait for Pairing successful)"
  exit 1
fi

bluetoothctl info "$MAC" 2>/dev/null | head -14 || true
echo ""
echo "Test in webui. Reconnect: Fn+$SLOT"
