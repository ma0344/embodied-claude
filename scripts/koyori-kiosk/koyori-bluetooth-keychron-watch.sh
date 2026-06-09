#!/usr/bin/env bash
# Background: reconnect Keychron when disconnected. Source from koyori-kiosk.sh.

koyori_bt_watch_log() {
  echo "$(date -Is) bt-watch: $*"
}

if [[ "${KOYORI_BT_AUTOCONNECT:-1}" != "1" ]]; then
  koyori_bt_watch_log "disabled (KOYORI_BT_AUTOCONNECT=0)"
  return 0
fi

if ! command -v bluetoothctl >/dev/null 2>&1; then
  koyori_bt_watch_log "WARN bluez missing"
  return 0
fi

LIB="/usr/local/bin/koyori-bluetooth-keychron-lib.sh"
[[ -f "$LIB" ]] || LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/koyori-bluetooth-keychron-lib.sh"
[[ -f "$LIB" ]] || {
  koyori_bt_watch_log "WARN lib missing"
  return 0
}
# shellcheck disable=SC1090
source "$LIB"

INTERVAL="${KOYORI_BT_RECONNECT_INTERVAL:-30}"
SCAN_SEC="${KOYORI_BT_WATCH_SCAN_SEC:-12}"

(
  sleep 10
  koyori_bt_watch_log "start interval=${INTERVAL}s"
  while true; do
    if ! koyori_keychron_is_connected; then
      if koyori_keychron_connect "$SCAN_SEC" >/tmp/koyori-bt-watch-last.log 2>&1; then
        koyori_bt_watch_log "$(head -1 /tmp/koyori-bt-watch-last.log)"
      fi
    fi
    sleep "$INTERVAL"
  done
) &

koyori_bt_watch_log "background pid=$!"
