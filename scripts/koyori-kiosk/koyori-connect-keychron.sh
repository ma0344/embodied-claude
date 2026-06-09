#!/usr/bin/env bash
# Reconnect Keychron without relying on a fixed MAC (K4 MAX random address).
#
# Usage: koyori-connect-keychron.sh
# On keyboard: Fn+<slot> for koyori (default slot 2).

set -euo pipefail

SLOT=2
NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-Keychron}"
if [[ -f ~/.config/koyori-keychron ]]; then
  # shellcheck disable=SC1090
  source ~/.config/koyori-keychron
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "bluez not installed" >&2
  exit 1
fi

echo "Turn on keyboard slot $SLOT (Fn+$SLOT), then waiting ..."
bluetoothctl power on >/dev/null 2>&1 || true

# Try last bonded device first
if [[ -n "${LAST_MAC:-}" ]]; then
  if bluetoothctl connect "$LAST_MAC" 2>/dev/null; then
    sleep 1
    if bluetoothctl info "$LAST_MAC" 2>/dev/null | grep -q "Connected: yes"; then
      echo "Connected via last MAC $LAST_MAC"
      exit 0
    fi
  fi
fi

# Scan and connect by name
bluetoothctl scan on >/dev/null 2>&1 || true
sleep 12
bluetoothctl scan off >/dev/null 2>&1 || true

MAC=$(bluetoothctl devices 2>/dev/null | grep -i "$NAME_PATTERN" | awk '{print $2}' | tail -1)
if [[ -z "$MAC" ]]; then
  echo "No '$NAME_PATTERN' found. Is Fn+$SLOT on and keyboard awake?" >&2
  bluetoothctl devices
  exit 1
fi

bluetoothctl trust "$MAC" 2>/dev/null || true
bluetoothctl connect "$MAC"
echo "Connected $MAC ($(bluetoothctl devices | grep "$MAC" || true))"

mkdir -p ~/.config
if [[ -f ~/.config/koyori-keychron ]]; then
  sed -i "s/^LAST_MAC=.*/LAST_MAC=$MAC/" ~/.config/koyori-keychron 2>/dev/null || true
fi
