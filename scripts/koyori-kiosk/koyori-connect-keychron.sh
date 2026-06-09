#!/usr/bin/env bash
# Reconnect Keychron (K4 MAX random MAC) by scanning for name.

set -euo pipefail

SLOT=2
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"
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
  mac=$(grep -iE '^\[(NEW|CHG)\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | tail -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  return 1
}

echo "Fn+$SLOT on keyboard, then scanning for *${NAME_PATTERN}* ..."
bluetoothctl power on >/dev/null 2>&1 || true

if [[ -n "${LAST_MAC:-}" ]]; then
  if bluetoothctl connect "$LAST_MAC" 2>/dev/null && \
     bluetoothctl info "$LAST_MAC" 2>/dev/null | grep -q 'Connected: yes'; then
    echo "Connected via last MAC $LAST_MAC"
    exit 0
  fi
fi

SCAN_LOG=$(mktemp)
trap 'rm -f "$SCAN_LOG"' EXIT

if bluetoothctl --help 2>&1 | grep -q -- '--timeout'; then
  bluetoothctl --timeout 20 scan on 2>&1 | tee -a "$SCAN_LOG" || true
else
  timeout 20 bluetoothctl scan on 2>&1 | tee -a "$SCAN_LOG" || true
  bluetoothctl scan off 2>&1 | tee -a "$SCAN_LOG" || true
fi
bluetoothctl devices 2>&1 | tee -a "$SCAN_LOG" || true

MAC=$(koyori_bt_find_mac "$NAME_PATTERN" "$SCAN_LOG" || true)
if [[ -z "$MAC" ]]; then
  echo "Not found. Is Fn+$SLOT on?" >&2
  grep -iE '^\[(NEW|CHG)\] Device|^Device ' "$SCAN_LOG" | tail -15
  exit 1
fi

bluetoothctl trust "$MAC" 2>/dev/null || true
bluetoothctl connect "$MAC"
echo "Connected $MAC"

if [[ -f ~/.config/koyori-keychron ]]; then
  sed -i "s/^LAST_MAC=.*/LAST_MAC=$MAC/" ~/.config/koyori-keychron 2>/dev/null || true
fi
