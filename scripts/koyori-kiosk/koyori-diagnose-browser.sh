#!/usr/bin/env bash
# Diagnose Firefox kiosk visibility on koyori (SSH while session on :0).
#
#   DISPLAY=:0 koyori-diagnose-browser

set -euo pipefail

UID_NUM=$(id -u)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi
export DISPLAY="${DISPLAY:-:0}"

echo "==> koyori browser diagnose"
echo "    user=$USER DISPLAY=$DISPLAY"
echo ""

if pgrep -u "$UID_NUM" -f '[f]irefox.*koyori-kiosk' >/dev/null; then
  echo "  firefox kiosk: running"
  pgrep -a -u "$UID_NUM" -f '[f]irefox.*koyori-kiosk' | sed 's/^/    /'
else
  echo "  firefox kiosk: NOT running"
  pgrep -a -u "$UID_NUM" firefox 2>/dev/null | sed 's/^/    /' || echo "    (no firefox)"
fi

echo ""
if command -v xset >/dev/null 2>&1; then
  echo "  xset q (dpms):"
  xset q 2>/dev/null | sed -n '/DPMS/,+3p' | sed 's/^/    /' || true
fi

echo ""
if command -v xdotool >/dev/null 2>&1; then
  mapfile -t wins < <(xdotool search --class Firefox 2>/dev/null || true)
  if ((${#wins[@]} == 0)); then
    echo "  xdotool: no Firefox window (class Firefox)"
    mapfile -t wins < <(xdotool search --class Navigator 2>/dev/null || true)
  fi
  if ((${#wins[@]} == 0)); then
    echo "  xdotool: no Navigator window either"
  else
    echo "  xdotool windows:"
    for wid in "${wins[@]}"; do
      echo "    id=$wid name=$(xdotool getwindowname "$wid" 2>/dev/null || echo '?')"
      xdotool getwindowgeometry --shell "$wid" 2>/dev/null | sed 's/^/      /' || true
      if command -v xwininfo >/dev/null 2>&1; then
        xwininfo -id "$wid" 2>/dev/null | awk '/Map State|Width:|Height:|Absolute|Depth/ {print "     ", $0}' || true
      fi
    done
  fi
else
  echo "  xdotool: missing (apt install xdotool)"
fi

echo ""
echo "  recent kiosk browser lines:"
if [[ -f /tmp/koyori-kiosk.log ]]; then
  grep -E 'browser=|firefox |display: browser|display: resized|display: WARN no browser' /tmp/koyori-kiosk.log \
    | tail -12 | sed 's/^/    /' || echo "    (none)"
else
  echo "    /tmp/koyori-kiosk.log missing"
fi

echo ""
echo "Quick fixes:"
echo "  DISPLAY=:0 xset dpms force on"
echo "  DISPLAY=:0 xdotool search --class Firefox windowactivate %1 windowraise %1"
echo "  sudo cp .../firefox-kiosk-user.js ~/snap/firefox/common/.mozilla/koyori-kiosk/user.js"
echo "  pkill -u $USER firefox; sudo reboot"
echo "  /etc/default/koyori-kiosk: KOYORI_FIREFOX_SOFTWARE_GL=1  # if still black"
