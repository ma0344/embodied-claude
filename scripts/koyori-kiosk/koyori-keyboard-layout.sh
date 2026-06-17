#!/usr/bin/env bash
# Show keyboard layout chart (GNOME Keyboard Viewer style). Read-only — not for typing.
#
#   koyori-keyboard-layout          # current XKB layout
#   koyori-keyboard-layout jp       # Japan
#   koyori-keyboard-layout us       # US (Input Leap routing reference)

set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if ! command -v gkbd-keyboard-display >/dev/null 2>&1; then
  echo "Install: sudo apt install -y gkbd-capplet" >&2
  exit 1
fi

layout="${1:-}"
variant="${2:-}"

if [[ -z "$layout" ]] && command -v setxkbmap >/dev/null 2>&1; then
  layout=$(setxkbmap -query 2>/dev/null | awk '/layout:/ {print $2; exit}')
  variant=$(setxkbmap -query 2>/dev/null | awk '/variant:/ {print $2; exit}')
fi

layout="${layout:-jp}"

if [[ -n "$variant" ]]; then
  exec gkbd-keyboard-display -l "${layout}"$'\t'"${variant}"
fi

exec gkbd-keyboard-display -l "$layout"
