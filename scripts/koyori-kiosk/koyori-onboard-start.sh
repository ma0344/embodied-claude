#!/usr/bin/env bash
# On-screen keyboard for Surface Go kiosk. Source from koyori-kiosk.sh (do not exec).
# Default: florence (--keep-above). Alternative: onboard (no dock-expand — hidden under Firefox).

koyori_osk_log() {
  echo "$(date -Is) osk: $*"
}

koyori_osk_geometry() {
  local w="${KOYORI_SCREEN_W:-1800}"
  local h_total="${KOYORI_SCREEN_H:-1200}"
  local h_kb="${KOYORI_ONBOARD_HEIGHT:-220}"
  local y=$((h_total - h_kb))
  printf '%s %s %s' "$w" "$h_kb" "$y"
}

koyori_osk_place_window() {
  local w h_kb y wid
  read -r w h_kb y < <(koyori_osk_geometry)
  command -v xdotool >/dev/null 2>&1 || return 0

  local i cls
  for i in $(seq 1 30); do
    for cls in Florence onboard Onboard; do
      wid=$(xdotool search --class "$cls" --onlyvisible 2>/dev/null | tail -1)
      [[ -n "$wid" ]] && break 2
    done
    sleep 0.2
  done
  [[ -n "$wid" ]] || {
    koyori_osk_log "WARN no OSK window for xdotool (classes: Florence/onboard)"
    return 1
  }

  xdotool windowmove "$wid" 0 "$y" 2>/dev/null || true
  xdotool windowsize "$wid" "$w" "$h_kb" 2>/dev/null || true
  xdotool windowraise "$wid" 2>/dev/null || true
  koyori_osk_log "placed window=$wid ${w}x${h_kb}+0+${y}"
}

koyori_onboard_configure() {
  if ! command -v gsettings >/dev/null 2>&1; then
    return 0
  fi
  local height="${KOYORI_ONBOARD_HEIGHT:-220}"
  gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true
  gsettings set org.onboard.auto-show enabled false 2>/dev/null || true
  gsettings set org.onboard.auto-show tablet-mode false 2>/dev/null || true
  # dock-expand hides under Firefox fullscreen; force-to-top + manual placement instead.
  gsettings set org.onboard.window.landscape dock-expand false 2>/dev/null || true
  gsettings set org.onboard.window force-to-top true 2>/dev/null || true
  gsettings set org.onboard.icon-palette in-use true 2>/dev/null || true
  gsettings set org.onboard.keyboard key-synth 'XTest' 2>/dev/null || true
  gsettings set org.onboard layout "${KOYORI_ONBOARD_LAYOUT:-Compact}" 2>/dev/null || true
  gsettings set org.onboard.window.landscape height "$height" 2>/dev/null || true
}

koyori_onboard_show() {
  local i
  for i in $(seq 1 40); do
    if dbus-send --print-reply --dest=org.onboard.Onboard /org/onboard/Onboard/Keyboard \
      org.freedesktop.DBus.Introspectable.Introspect >/dev/null 2>&1; then
      dbus-send --type=method_call --dest=org.onboard.Onboard /org/onboard/Onboard/Keyboard \
        org.onboard.Onboard.Keyboard.Show >/dev/null 2>&1 || true
      return 0
    fi
    sleep 0.15
  done
  koyori_osk_log "WARN onboard dbus Show timed out"
  return 1
}

koyori_osk_start_florence() {
  if ! command -v florence >/dev/null 2>&1; then
    koyori_osk_log "WARN florence not installed — apt install florence"
    return 1
  fi
  if pgrep -u "$(id -u)" -f "[f]lorence" >/dev/null 2>&1; then
    koyori_osk_log "florence already running"
    return 0
  fi
  local w h_kb y
  read -r w h_kb y < <(koyori_osk_geometry)
  florence --daemon --keep-above --no-gnome --geometry "${w}x${h_kb}+0+${y}" &
  sleep 0.5
  koyori_osk_place_window || true
  koyori_osk_log "florence started ${w}x${h_kb}+0+${y}"
}

koyori_osk_start_onboard() {
  if ! command -v onboard >/dev/null 2>&1; then
    koyori_osk_log "WARN onboard not installed — apt install onboard"
    return 1
  fi

  export GTK_A11Y=1
  export NO_AT_BRIDGE=0
  if command -v at-spi-bus-launcher >/dev/null 2>&1; then
    if ! pgrep -u "$(id -u)" -f at-spi-bus-launcher >/dev/null 2>&1; then
      at-spi-bus-launcher --launch-only &
      sleep 0.3
    fi
  fi

  koyori_onboard_configure

  if ! pgrep -u "$(id -u)" -x onboard >/dev/null 2>&1; then
    onboard --quirks=metacity &
    sleep 0.5
  fi

  if ! pgrep -u "$(id -u)" -x onboard >/dev/null 2>&1; then
    koyori_osk_log "ERROR onboard exited immediately"
    return 1
  fi

  koyori_onboard_show || true
  koyori_osk_place_window || true
  koyori_osk_log "onboard started (force-to-top, no dock-expand)"
}

# Called again after Firefox goes fullscreen.
koyori_osk_ensure_visible() {
  local backend="${KOYORI_OSK_BACKEND:-florence}"
  if [[ "$backend" == "onboard" ]]; then
    koyori_onboard_show || true
  fi
  koyori_osk_place_window || true
}

if [[ "${KOYORI_ONBOARD:-0}" != "1" ]]; then
  koyori_osk_log "disabled (KOYORI_ONBOARD=0)"
  return 0
fi

backend="${KOYORI_OSK_BACKEND:-florence}"
case "$backend" in
  florence)
    koyori_osk_start_florence || koyori_osk_start_onboard || true
    ;;
  onboard)
    koyori_osk_start_onboard || koyori_osk_start_florence || true
    ;;
  *)
    koyori_osk_log "WARN unknown KOYORI_OSK_BACKEND=$backend (use florence|onboard)"
    ;;
esac
