#!/usr/bin/env bash
# Configure X display for kiosk fullscreen. Source from koyori-kiosk.sh (do not exec).

koyori_display_log() {
  echo "$(date -Is) display: $*"
}

koyori_display_log "start DISPLAY=${DISPLAY:-unset}"

if command -v xsetroot >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  xsetroot -solid "#000000" || true
fi

if command -v xrandr >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  primary=""
  while read -r output _rest; do
    [[ -z "$output" ]] && continue
    xrandr --output "$output" --auto 2>/dev/null || true
    [[ -z "$primary" ]] && primary="$output"
  done < <(xrandr | awk '/ connected/{print $1}')

  if [[ -n "$primary" ]]; then
    xrandr --output "$primary" --primary 2>/dev/null || true
    if [[ -n "${KOYORI_DISPLAY_MODE:-}" ]]; then
      if xrandr --output "$primary" --mode "$KOYORI_DISPLAY_MODE" 2>/dev/null; then
        koyori_display_log "mode=$KOYORI_DISPLAY_MODE output=$primary"
      else
        koyori_display_log "WARN could not set mode $KOYORI_DISPLAY_MODE on $primary"
      fi
    fi
    koyori_display_log "primary=$primary current=$(xrandr | awk -v o="$primary" '$1==o{print; getline; print}' | tr '\n' ' ')"
  else
    koyori_display_log "WARN no connected outputs in xrandr"
  fi
else
  koyori_display_log "WARN xrandr unavailable"
fi

if command -v xdpyinfo >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  dims=$(xdpyinfo | awk '/dimensions:/{print $2; exit}')
  if [[ -n "$dims" ]]; then
    export KOYORI_SCREEN_W="${dims%x*}"
    export KOYORI_SCREEN_H="${dims#*x}"
    koyori_display_log "dimensions=${KOYORI_SCREEN_W}x${KOYORI_SCREEN_H}"
  fi
fi

koyori_start_window_manager() {
  if [[ "${KOYORI_USE_WM:-1}" != "1" ]]; then
    return 0
  fi
  if command -v openbox >/dev/null 2>&1; then
    openbox --sm-disable &
    sleep 0.3
    koyori_display_log "wm=openbox"
    return 0
  fi
  koyori_display_log "WARN openbox not installed (apt install openbox)"
}

# Resize browser window to root size (Firefox --kiosk often stays smaller without a WM).
koyori_raise_browser_window() {
  local wid="$1"
  local w="${KOYORI_SCREEN_W:-}"
  local h="${KOYORI_SCREEN_H:-}"
  command -v xdotool >/dev/null 2>&1 || return 0
  [[ -n "$wid" ]] || return 0

  xdotool windowmap "$wid" 2>/dev/null || true
  xdotool windowactivate "$wid" 2>/dev/null || true
  xdotool windowraise "$wid" 2>/dev/null || true
  if [[ -n "$w" && -n "$h" ]]; then
    xdotool windowmove "$wid" 0 0 2>/dev/null || true
    xdotool windowsize "$wid" "$w" "$h" 2>/dev/null || true
  fi
  if command -v wmctrl >/dev/null 2>&1; then
    wmctrl -i -r "$wid" -b add,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true
  fi
}

koyori_resize_browser_window() {
  local browser_pid="${1:-}"
  local w="${KOYORI_SCREEN_W:-}"
  local h="${KOYORI_SCREEN_H:-}"

  [[ -n "$w" && -n "$h" ]] || return 0
  command -v xdotool >/dev/null 2>&1 || {
    koyori_display_log "WARN xdotool missing — skip window resize"
    return 0
  }

  local wid="" i
  for i in $(seq 1 80); do
    if [[ -n "$browser_pid" ]] && kill -0 "$browser_pid" 2>/dev/null; then
      wid=$(xdotool search --pid "$browser_pid" 2>/dev/null | head -1)
    fi
    for cls in Firefox Navigator firefox; do
      if [[ -z "$wid" ]]; then
        wid=$(xdotool search --class "$cls" 2>/dev/null | tail -1)
      fi
    done
    [[ -n "$wid" ]] && break
    sleep 0.25
  done

  if [[ -z "$wid" ]]; then
    koyori_display_log "WARN no browser window found for resize"
    return 0
  fi

  koyori_raise_browser_window "$wid"
  local geom
  geom=$(xdotool getwindowgeometry --shell "$wid" 2>/dev/null || true)
  koyori_display_log "browser window=$wid geometry=${geom//$'\n'/ } target=${w}x${h}"
}
