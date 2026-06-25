#!/usr/bin/env bash
# Restart Firefox without --kiosk (fixes 1x1 snap windows on Surface).
#
#   DISPLAY=:0 koyori-restart-browser

set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

if [[ -f /etc/default/koyori-kiosk ]]; then
  # shellcheck disable=SC1091
  source /etc/default/koyori-kiosk
fi

WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8090/}"
WEBUI_URL="${WEBUI_URL//kiosk=0/kiosk=1}"
if [[ "$WEBUI_URL" != *kiosk=* ]]; then
  if [[ "$WEBUI_URL" == *\?* ]]; then
    WEBUI_URL="${WEBUI_URL}&kiosk=1"
  else
    WEBUI_URL="${WEBUI_URL%/}?kiosk=1"
  fi
fi

if [[ -d "${HOME}/snap/firefox/common" ]]; then
  FF_PROFILE="${HOME}/snap/firefox/common/.mozilla/koyori-kiosk"
else
  FF_PROFILE="${HOME}/.mozilla/koyori-kiosk"
fi

echo "stopping firefox..."
pkill -u "$(id -u)" -x firefox 2>/dev/null || pkill -u "$(id -u)" -f 'firefox.*koyori-kiosk' 2>/dev/null || true
sleep 2

rm -f "${FF_PROFILE}/.parentlock" "${FF_PROFILE}/lock" "${FF_PROFILE}/parent.lock" 2>/dev/null || true

args=(--profile "$FF_PROFILE")
if [[ "${KOYORI_FIREFOX_KIOSK_FLAG:-0}" == "1" ]]; then
  args+=(--kiosk)
fi

echo "launch: firefox ${args[*]} $WEBUI_URL"
firefox "${args[@]}" "$WEBUI_URL" </dev/null &
sleep 4

if [[ -x /usr/local/bin/koyori-fix-browser-window ]]; then
  /usr/local/bin/koyori-fix-browser-window
elif [[ -f /usr/local/bin/koyori-display-setup ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-display-setup
  pid=$(pgrep -u "$(id -u)" -n -f '[f]irefox.*koyori-kiosk' 2>/dev/null || true)
  koyori_resize_browser_window "$pid"
fi

pgrep -a -u "$(id -u)" firefox || echo "WARN: firefox not running"
