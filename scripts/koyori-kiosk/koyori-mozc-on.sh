#!/usr/bin/env bash
# Switch koyori kiosk to Mozc (Japanese). Useful when 半/全 does not arrive via Input Leap.
#
#   koyori-mozc-on
#   DISPLAY=:0 koyori-mozc-on

set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
  echo "ibus-daemon not running — start kiosk session first" >&2
  exit 1
fi

while IFS= read -r engine; do
  [[ -z "$engine" ]] && continue
  if ibus engine "$engine" 2>/dev/null; then
    echo "engine=$(ibus engine 2>/dev/null || echo "$engine")"
    echo "type romaji (konnichiwa + Space). Input Leap: click IBUS panel あ if still A_"
    exit 0
  fi
done < <(ibus list-engine 2>/dev/null | awk '/mozc/ { print $1 }' | sort -u)

echo "failed to activate mozc — run koyori-diagnose-ime" >&2
exit 1
