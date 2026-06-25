#!/usr/bin/env bash
# Expand Firefox 1x1 kiosk windows on a running session (SSH ok).
#
#   DISPLAY=:0 koyori-fix-browser-window

set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
source /usr/local/bin/koyori-display-setup 2>/dev/null || source "$SCRIPT_DIR/koyori-display-setup.sh"

if command -v xdpyinfo >/dev/null 2>&1; then
  dims=$(xdpyinfo | awk '/dimensions:/{print $2; exit}')
  export KOYORI_SCREEN_W="${dims%x*}"
  export KOYORI_SCREEN_H="${dims#*x}"
fi

pid=$(pgrep -u "$(id -u)" -n -f '[f]irefox.*koyori-kiosk' 2>/dev/null || true)
echo "firefox pid=${pid:-none} screen=${KOYORI_SCREEN_W:-?}x${KOYORI_SCREEN_H:-?}"
koyori_resize_browser_window "$pid"
