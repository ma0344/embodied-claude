#!/usr/bin/env bash
# Reconnect Keychron by name (single bluetoothctl scan session).

set -euo pipefail

SLOT=2
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"
SCAN_SEC="${KOYORI_BT_SCAN_SEC:-20}"
if [[ -f ~/.config/koyori-keychron ]]; then
  # shellcheck disable=SC1090
  source ~/.config/koyori-keychron
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "bluez not installed" >&2
  exit 1
fi

koyori_bt_find_mac() {
  local pattern="$1"
  local log="$2"
  local mac=""
  mac=$(grep -iE '\[(NEW|CHG)\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | tail -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  return 1
}

if [[ -n "${LAST_MAC:-}" ]]; then
  if {
    echo "connect $LAST_MAC"
    echo quit
  } | bluetoothctl 2>/dev/null | grep -qi 'successful\|Connected'; then
    echo "Connected $LAST_MAC"
    exit 0
  fi
fi

echo "Fn+$SLOT on keyboard — scanning ${SCAN_SEC}s ..."
SCAN_LOG=$(mktemp)
trap 'rm -f "$SCAN_LOG"' EXIT

{
  echo power on
  echo scan on
  sleep "$SCAN_SEC"
  echo devices
  echo scan off
  echo quit
} | bluetoothctl 2>&1 | tee "$SCAN_LOG" || true

MAC=$(koyori_bt_find_mac "$NAME_PATTERN" "$SCAN_LOG" || true)
if [[ -z "$MAC" ]]; then
  echo "Not found (*${NAME_PATTERN}*)" >&2
  grep -iE '\[(NEW|CHG)\] Device|^Device [0-9A-F]' "$SCAN_LOG" | tail -15
  exit 1
fi

{
  echo "trust $MAC"
  echo "connect $MAC"
  echo quit
} | bluetoothctl 2>&1 | tee -a "$SCAN_LOG"

echo "Connected $MAC"
sed -i "s/^LAST_MAC=.*/LAST_MAC=$MAC/" ~/.config/koyori-keychron 2>/dev/null || true
