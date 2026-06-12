#
#!/usr/bin/env bash
# Minimal X session: Chromium fullscreen → ma-home presence-ui (こよりの部屋).

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

WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home:8090/projects/C:/Users/ma/src/embodied-claude}"

# Prefer IPv4 literal in /etc/default/koyori-kiosk if ma-home resolves to IPv6
# but presence-ui listens on IPv4 only (typical: 0.0.0.0:8090).
# Example: KOYORI_WEBUI_URL='http://192.168.10.50:8090/projects/C:/Users/ma/src/embodied-claude'

if command -v xset >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

if command -v unclutter >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  unclutter -idle 0 -root &
fi

if [[ -x /usr/local/bin/koyori-display-setup ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-display-setup
  koyori_start_window_manager
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

if [[ -x /usr/local/bin/koyori-input-leap-start ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-input-leap-start
fi

if [[ -x /usr/local/bin/koyori-onboard-start ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-onboard-start
fi

if [[ -x /usr/local/bin/koyori-bluetooth-keychron-watch ]]; then
  # shellcheck disable=SC1091
  source /usr/local/bin/koyori-bluetooth-keychron-watch
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

koyori_run_browser() {
  local browser_pid

  if [[ "$CHROMIUM" == *firefox* ]]; then
    export MOZ_ENABLE_A11Y=1
    local ff_args=(--kiosk)
    local ff_profile="${KOYORI_FIREFOX_PROFILE:-}"
    if [[ -z "$ff_profile" ]]; then
      if [[ -d "${HOME}/snap/firefox/common" ]]; then
        ff_profile="${HOME}/snap/firefox/common/.mozilla/koyori-kiosk"
      else
        ff_profile="${HOME}/.mozilla/koyori-kiosk"
      fi
    fi
    if [[ -d "$ff_profile" && -r "$ff_profile" && -w "$ff_profile" ]]; then
      ff_args=(--profile "$ff_profile" --kiosk)
      log "firefox profile=$ff_profile"
    else
      log "WARN firefox profile unavailable ($ff_profile) — default profile"
    fi
    "$CHROMIUM" "${ff_args[@]}" "$WEBUI_URL" &
    browser_pid=$!
    if declare -F koyori_resize_browser_window >/dev/null 2>&1; then
      (sleep 2; koyori_resize_browser_window "$browser_pid") &
    fi
    if declare -F koyori_osk_ensure_visible >/dev/null 2>&1; then
      (sleep 3; koyori_osk_ensure_visible) &
    fi
    wait "$browser_pid"
    return $?
  fi

  # Ubuntu 24.04 chromium-browser is usually snap; needs this on minimal X sessions.
  if [[ "${KOYORI_CHROMIUM_NO_SANDBOX:-1}" == "1" ]]; then
    BROWSER_ARGS+=(--no-sandbox)
  fi
  BROWSER_ARGS+=(--ozone-platform=x11 --start-fullscreen --window-position=0,0)
  if [[ -n "${KOYORI_SCREEN_W:-}" && -n "${KOYORI_SCREEN_H:-}" ]]; then
    BROWSER_ARGS+=(--window-size="${KOYORI_SCREEN_W},${KOYORI_SCREEN_H}")
  fi

  "$CHROMIUM" "${BROWSER_ARGS[@]}" "$WEBUI_URL" &
  browser_pid=$!
  if declare -F koyori_resize_browser_window >/dev/null 2>&1; then
    (sleep 2; koyori_resize_browser_window "$browser_pid") &
  fi
  if declare -F koyori_osk_ensure_visible >/dev/null 2>&1; then
    (sleep 3; koyori_osk_ensure_visible) &
  fi
  wait "$browser_pid"
}

koyori_run_browser
