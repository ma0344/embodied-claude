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

# firefox: reliable IBus on minimal X. chromium snap often ignores host IME.
KOYORI_BROWSER="${KOYORI_BROWSER:-auto}"

pick_browser() {
  local want="$1"
  local c

  if [[ "$want" == "firefox" ]]; then
    for c in firefox firefox-esr; do command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }; done
    return 1
  fi
  if [[ "$want" == "chromium" ]]; then
    for c in chromium-browser chromium google-chrome; do
      command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }
    done
    return 1
  fi
  # auto: prefer firefox for Japanese IME
  for c in firefox firefox-esr; do command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }; done
  for c in chromium-browser chromium google-chrome; do
    command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }
  done
  return 1
}

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
if picked=$(pick_browser "$KOYORI_BROWSER"); then
  CHROMIUM="$picked"
fi

if [[ -z "$CHROMIUM" ]]; then
  log "ERROR: no browser found (KOYORI_BROWSER=$KOYORI_BROWSER)"
  exit 1
fi

log "browser=$CHROMIUM (KOYORI_BROWSER=$KOYORI_BROWSER) url=$WEBUI_URL"

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
  exec "$CHROMIUM" --kiosk "$WEBUI_URL"
fi

# Ubuntu 24.04 chromium-browser is usually snap; needs this on minimal X sessions.
if [[ "${KOYORI_CHROMIUM_NO_SANDBOX:-1}" == "1" ]]; then
  BROWSER_ARGS+=(--no-sandbox)
fi
# Snap chromium + IBus: X11 ozone sometimes helps; firefox is still preferred.
BROWSER_ARGS+=(--ozone-platform=x11)

exec "$CHROMIUM" "${BROWSER_ARGS[@]}" "$WEBUI_URL"
