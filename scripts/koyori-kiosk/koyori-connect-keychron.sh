#!/usr/bin/env bash
# Reconnect Keychron K4 MAX. Press Fn+2 on keyboard, then run (or use watch daemon).

set -euo pipefail

LIB="/usr/local/bin/koyori-bluetooth-keychron-lib.sh"
[[ -f "$LIB" ]] || LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/koyori-bluetooth-keychron-lib.sh"
# shellcheck disable=SC1090
source "$LIB"

SCAN_SEC="${KOYORI_BT_SCAN_SEC:-25}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as user ma." >&2
  exit 1
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "sudo apt install -y bluez" >&2
  exit 1
fi

koyori_keychron_load_config
echo "Keychron reconnect (slot $SLOT) — press Fn+$SLOT on keyboard now ..."
echo "Scan ${SCAN_SEC}s if paired MAC reconnect fails."

if koyori_keychron_connect "$SCAN_SEC"; then
  bluetoothctl devices 2>/dev/null | grep -i keychron || true
  exit 0
fi

echo "Failed. Try:" >&2
echo "  1. Fn+$SLOT (keyboard awake, USB unplugged)" >&2
echo "  2. koyori-pair-keychron.sh $SLOT  (re-pair)" >&2
exit 1
