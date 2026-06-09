#!/usr/bin/env bash
# On-screen keyboard for Surface Go kiosk. Source from koyori-kiosk.sh (do not exec).

koyori_onboard_log() {
  echo "$(date -Is) onboard: $*"
}

if [[ "${KOYORI_ONBOARD:-1}" != "1" ]]; then
  koyori_onboard_log "disabled (KOYORI_ONBOARD=0)"
  return 0
fi

if ! command -v onboard >/dev/null 2>&1; then
  koyori_onboard_log "WARN onboard not installed — apt install onboard"
  return 0
fi

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.onboard.auto-show enabled true 2>/dev/null || true
  gsettings set org.onboard.auto-show tablet-mode true 2>/dev/null || true
  gsettings set org.onboard.window.force-to-top true 2>/dev/null || true
  gsettings set org.onboard.icon-palette in-use true 2>/dev/null || true
  gsettings set org.onboard.icon-palette hide-on-touch false 2>/dev/null || true
  # org.onboard.layout — Compact / Full Keyboard など
  gsettings set org.onboard.window.landscape dock-expand true 2>/dev/null || true
  gsettings set org.onboard.window.landscape dock-height "${KOYORI_ONBOARD_HEIGHT:-220}" 2>/dev/null || true
  gsettings set org.onboard layout "${KOYORI_ONBOARD_LAYOUT:-Compact}" 2>/dev/null || true
fi

if pgrep -u "$(id -u)" -x onboard >/dev/null 2>&1; then
  koyori_onboard_log "already running"
  return 0
fi

onboard &
koyori_onboard_log "started (tap text field or palette icon; auto-show on focus)"
