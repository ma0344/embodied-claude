#!/usr/bin/env bash
# Minimal X session: Chromium fullscreen → ma-home claude-code-webui.

log() {
  echo "$(date -Is) $*"
}

LOG="/tmp/koyori-kiosk.log"
exec >>"$LOG" 2>&1

log "koyori-kiosk start uid=$(id -u) DISPLAY=${DISPLAY:-unset} HOME=${HOME:-unset}"

if [[ -f /etc/default/koyori-kiosk ]]; then
  # shellcheck disable=SC1091
  source /etc/default/koyori-kiosk
fi

: "${XDG_RUNTIME_DIR:=/run/user/$(id -u)}"
export XDG_RUNTIME_DIR
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8080/projects/C:/Users/ma/src/embodied-claude}"

# Prefer IPv4 literal in /etc/default/koyori-kiosk if ma-home.local resolves to IPv6
# but ma-home webui listens on IPv4 only (typical: 0.0.0.0:8080).
# Example: KOYORI_WEBUI_URL='http://192.168.10.50:8080/projects/C:/Users/ma/src/embodied-claude'

if command -v xset >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

if command -v unclutter >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  unclutter -idle 0 -root &
fi

CHROMIUM=""
for candidate in chromium-browser chromium google-chrome firefox; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CHROMIUM="$candidate"
    break
  fi
done

if [[ -z "$CHROMIUM" ]]; then
  log "ERROR: no browser binary found (chromium/firefox)"
  exit 1
fi

log "browser=$CHROMIUM url=$WEBUI_URL"

if [[ -x /usr/local/bin/koyori-ime-start ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-ime-start
fi

BROWSER_ARGS=(
  --kiosk
  --noerrdialogs
  --disable-infobars
  --no-first-run
  --disable-session-crashed-bubble
  --disable-translate
  --autoplay-policy=no-user-gesture-required
)

if [[ "$CHROMIUM" == *firefox* ]]; then
  BROWSER_ARGS=(--kiosk "$WEBUI_URL")
  exec "$CHROMIUM" "${BROWSER_ARGS[@]}"
fi

# Ubuntu 24.04 chromium-browser is usually snap; needs this on minimal X sessions.
if [[ "${KOYORI_CHROMIUM_NO_SANDBOX:-1}" == "1" ]]; then
  BROWSER_ARGS+=(--no-sandbox)
fi

exec "$CHROMIUM" "${BROWSER_ARGS[@]}" "$WEBUI_URL"
