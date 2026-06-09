#!/usr/bin/env bash
# On-screen keyboard for Surface Go kiosk. Source from koyori-kiosk.sh (do not exec).
# Always-visible dock (no auto-show) — avoids GNOME accessibility Yes/No dialog.

koyori_onboard_log() {
  echo "$(date -Is) onboard: $*"
}

koyori_onboard_configure() {
  if ! command -v gsettings >/dev/null 2>&1; then
    return 0
  fi
  local height="${KOYORI_ONBOARD_HEIGHT:-220}"
  gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true
  gsettings set org.onboard.auto-show enabled false 2>/dev/null || true
  gsettings set org.onboard.auto-show tablet-mode false 2>/dev/null || true
  gsettings set org.onboard.window.force-to-top true 2>/dev/null || true
  gsettings set org.onboard.icon-palette in-use true 2>/dev/null || true
  gsettings set org.onboard.window.landscape dock-expand true 2>/dev/null || true
  gsettings set org.onboard.window.landscape dock-height "$height" 2>/dev/null || true
  gsettings set org.onboard.keyboard key-synth 'XTest' 2>/dev/null || true
  gsettings set org.onboard layout "${KOYORI_ONBOARD_LAYOUT:-Compact}" 2>/dev/null || true
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
  koyori_onboard_log "WARN dbus Show timed out"
  return 1
}

if [[ "${KOYORI_ONBOARD:-1}" != "1" ]]; then
  koyori_onboard_log "disabled (KOYORI_ONBOARD=0)"
  return 0
fi

if ! command -v onboard >/dev/null 2>&1; then
  koyori_onboard_log "WARN onboard not installed — apt install onboard"
  return 0
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

if pgrep -u "$(id -u)" -x onboard >/dev/null 2>&1; then
  koyori_onboard_show || true
  koyori_onboard_log "already running — show requested"
  return 0
fi

onboard &
koyori_onboard_show || true
koyori_onboard_log "started (docked keyboard; palette icon toggles hide/show)"
