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
# lightdm/Xsession 経由で未設定のことがある
export DISPLAY="${DISPLAY:-:0}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

# presence-ui root (/) — NOT /projects/... (8080 SPA path; 8090 returns JSON 404 in Firefox)
WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8090/}"

# C7/C11: dedicated kiosk session always uses touch layout (?kiosk=1).
# Never honor kiosk=0 (PC layout breaks Surface touch UX / C11b drawer).
WEBUI_URL="${WEBUI_URL//kiosk=0/kiosk=1}"
if [[ "$WEBUI_URL" != *kiosk=* ]]; then
  if [[ "$WEBUI_URL" == *\?* ]]; then
    WEBUI_URL="${WEBUI_URL}&kiosk=1"
  else
    WEBUI_URL="${WEBUI_URL%/}?kiosk=1"
  fi
fi

# Prefer IPv4 literal in /etc/default/koyori-kiosk if ma-home.local resolves to IPv6
# but presence-ui listens on IPv4 only (typical: 0.0.0.0:8090).
# Example: KOYORI_WEBUI_URL='http://192.168.10.50:8090/'

koyori_configure_dpms() {
  command -v xset >/dev/null 2>&1 || return 0
  [[ -n "${DISPLAY:-}" ]] || return 0
  local off_sec="${KOYORI_DPMS_OFF_SEC:-60}"
  # C11g: wakeLock 解除後に OS が消灯できるよう DPMS を有効化（旧: xset -dpms で常時点灯固定）
  xset s off 2>/dev/null || true
  xset +dpms 2>/dev/null || true
  xset dpms 0 0 "$off_sec" 2>/dev/null || true
  xset dpms force on 2>/dev/null || true
  log "dpms enabled standby_off_sec=$off_sec (forced on at boot)"
}

koyori_start_screen_idle_server() {
  local py="/usr/local/bin/koyori-screen-idle-server"
  local port="${KOYORI_SCREEN_IDLE_PORT:-18790}"
  if [[ ! -x "$py" ]]; then
    log "WARN screen-idle-server missing — run: sudo install-koyori-kiosk.sh"
    return 0
  fi
  if ss -ltn 2>/dev/null | grep -qE ":${port}\\b"; then
    log "screen-idle-server already listening on :${port}"
    return 0
  fi
  DISPLAY="$DISPLAY" "$py" &
  local pid=$!
  sleep 0.3
  if ! kill -0 "$pid" 2>/dev/null; then
    log "WARN screen-idle-server exited immediately (DISPLAY=$DISPLAY)"
    return 0
  fi
  if ! ss -ltn 2>/dev/null | grep -qE ":${port}\\b"; then
    log "WARN screen-idle-server pid=$pid but port :${port} not listening"
    return 0
  fi
  log "screen-idle-server pid=$pid port=$port"
}

if command -v xset >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  koyori_configure_dpms
fi

koyori_start_screen_idle_server

koyori_start_audio_server() {
  local py="/usr/local/bin/koyori-audio-server"
  local port="${KOYORI_AUDIO_PORT:-18791}"
  if [[ ! -x "$py" ]]; then
    log "WARN audio-server missing — run: sudo install-koyori-kiosk.sh"
    return 0
  fi
  if ss -ltn 2>/dev/null | grep -qE ":${port}\\b"; then
    log "audio-server already listening on :${port}"
    return 0
  fi
  KOYORI_AUDIO_USER="${KOYORI_AUDIO_USER:-ma}" "$py" &
  local pid=$!
  sleep 0.3
  if ! kill -0 "$pid" 2>/dev/null; then
    log "WARN audio-server exited immediately"
    return 0
  fi
  if ! ss -ltn 2>/dev/null | grep -qE ":${port}\\b"; then
    log "WARN audio-server pid=$pid but port :${port} not listening"
    return 0
  fi
  log "audio-server pid=$pid port=$port"
}

koyori_start_audio_server

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

# IME module env must be set before Firefox GTK init. Daemon startup runs in parallel.
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export CLUTTER_IM_MODULE=ibus
export SDL_IM_MODULE=ibus
export MOZ_ENABLE_WAYLAND=0
export GDK_BACKEND=x11

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

if [[ -x /usr/local/bin/koyori-ime-start ]]; then
  /usr/local/bin/koyori-ime-start &
  log "ime: background pid=$!"
fi

# Brief settle for openbox + first paint (regression: IME-before-browser hid snap Firefox).
sleep "${KOYORI_BROWSER_START_DELAY_SEC:-2}"

BROWSER_ARGS=(
  --kiosk
  --noerrdialogs
  --disable-infobars
  --no-first-run
  --disable-session-crashed-bubble
  --disable-translate
  --autoplay-policy=no-user-gesture-required
)

koyori_prepare_firefox_profile() {
  local ff_profile="$1"
  [[ -d "$ff_profile" ]] || return 0
  if pgrep -u "$(id -u)" -f '[f]irefox' >/dev/null 2>&1; then
    return 0
  fi
  rm -f "${ff_profile}/.parentlock" "${ff_profile}/lock" "${ff_profile}/parent.lock" 2>/dev/null || true
}

koyori_find_firefox_pid() {
  local pid
  for pid in $(pgrep -u "$(id -u)" -x firefox 2>/dev/null); do
    if tr '\0' ' ' </proc/"$pid"/cmdline 2>/dev/null | grep -qE 'koyori-kiosk'; then
      echo "$pid"
      return 0
    fi
  done
  pgrep -u "$(id -u)" -n -f '[f]irefox.*koyori-kiosk' 2>/dev/null || true
}

koyori_wait_firefox_exit() {
  local browser_pid="$1"
  while kill -0 "$browser_pid" 2>/dev/null; do
    sleep 2
  done
  wait "$browser_pid" 2>/dev/null || true
}

koyori_run_browser() {
  local browser_pid launcher_pid ff_args ff_profile

  if [[ "$CHROMIUM" == *firefox* ]]; then
    local existing_pid
    existing_pid=$(koyori_find_firefox_pid)
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      log "firefox already running pid=$existing_pid — waiting (no second launch)"
      if declare -F koyori_resize_browser_window >/dev/null 2>&1; then
        koyori_resize_browser_window "$existing_pid"
      fi
      koyori_wait_firefox_exit "$existing_pid"
      local rc=$?
      log "firefox exited pid=$existing_pid code=$rc"
      return "$rc"
    fi

    export MOZ_ENABLE_A11Y=1
    export MOZ_X11_EGL=0
    if [[ "${KOYORI_FIREFOX_SOFTWARE_GL:-0}" == "1" ]]; then
      export LIBGL_ALWAYS_SOFTWARE=1
      log "firefox software GL enabled (KOYORI_FIREFOX_SOFTWARE_GL=1)"
    fi
    ff_args=()
    # snap Firefox + minimal openbox: --kiosk often creates 1x1 helper windows (see xdotool).
    if [[ "${KOYORI_FIREFOX_KIOSK_FLAG:-0}" == "1" ]]; then
      ff_args+=(--kiosk)
    fi
    ff_profile="${KOYORI_FIREFOX_PROFILE:-}"
    if [[ -z "$ff_profile" ]]; then
      if [[ -d "${HOME}/snap/firefox/common" ]]; then
        ff_profile="${HOME}/snap/firefox/common/.mozilla/koyori-kiosk"
      else
        ff_profile="${HOME}/.mozilla/koyori-kiosk"
      fi
    fi
    if [[ -d "$ff_profile" && -r "$ff_profile" && -w "$ff_profile" ]]; then
      koyori_prepare_firefox_profile "$ff_profile"
      ff_args=(--profile "$ff_profile" "${ff_args[@]}")
      log "firefox profile=$ff_profile kiosk_flag=${KOYORI_FIREFOX_KIOSK_FLAG:-0}"
    else
      log "WARN firefox profile unavailable ($ff_profile) — default profile"
    fi
    log "firefox launch: $CHROMIUM ${ff_args[*]} $WEBUI_URL"
    "$CHROMIUM" "${ff_args[@]}" "$WEBUI_URL" </dev/null &
    launcher_pid=$!
    disown "$launcher_pid" 2>/dev/null || true

    browser_pid=""
    local i
    for i in $(seq 1 40); do
      browser_pid=$(koyori_find_firefox_pid)
      [[ -n "$browser_pid" ]] && break
      if ! kill -0 "$launcher_pid" 2>/dev/null; then
        wait "$launcher_pid" 2>/dev/null || true
        browser_pid=$(koyori_find_firefox_pid)
        break
      fi
      sleep 0.25
    done

    if [[ -z "$browser_pid" ]]; then
      log "ERROR firefox process not found after launch (launcher_pid=$launcher_pid)"
      wait "$launcher_pid" 2>/dev/null || true
      return 1
    fi
    log "firefox pid=$browser_pid (launcher=$launcher_pid)"

    if declare -F koyori_resize_browser_window >/dev/null 2>&1; then
      (sleep 2; koyori_resize_browser_window "$browser_pid") &
      (sleep 5; koyori_resize_browser_window "$browser_pid") &
      (sleep 10; koyori_resize_browser_window "$browser_pid") &
      (sleep 20; koyori_resize_browser_window "$browser_pid") &
    fi
    if declare -F koyori_osk_ensure_visible >/dev/null 2>&1; then
      (sleep 3; koyori_osk_ensure_visible) &
    fi
    koyori_wait_firefox_exit "$browser_pid"
    local rc=$?
    log "firefox exited pid=$browser_pid code=$rc"
    return "$rc"
  fi

  # Ubuntu 24.04 chromium-browser is usually snap; needs this on minimal X sessions.
  if [[ "${KOYORI_CHROMIUM_NO_SANDBOX:-1}" == "1" ]]; then
    BROWSER_ARGS+=(--no-sandbox)
  fi
  BROWSER_ARGS+=(--ozone-platform=x11 --start-fullscreen --window-position=0,0)
  if [[ -n "${KOYORI_SCREEN_W:-}" && -n "${KOYORI_SCREEN_H:-}" ]]; then
    BROWSER_ARGS+=(--window-size="${KOYORI_SCREEN_W},${KOYORI_SCREEN_H}")
  fi

  log "chromium launch: $CHROMIUM ${BROWSER_ARGS[*]} $WEBUI_URL"
  "$CHROMIUM" "${BROWSER_ARGS[@]}" "$WEBUI_URL" </dev/null &
  launcher_pid=$!
  disown "$launcher_pid" 2>/dev/null || true
  browser_pid=$launcher_pid
  if declare -F koyori_resize_browser_window >/dev/null 2>&1; then
    (sleep 2; koyori_resize_browser_window "$browser_pid") &
  fi
  if declare -F koyori_osk_ensure_visible >/dev/null 2>&1; then
    (sleep 3; koyori_osk_ensure_visible) &
  fi
  wait "$browser_pid"
  local rc=$?
  log "chromium exited pid=$browser_pid code=$rc"
  return "$rc"
}

BROWSER_RESTART_SEC="${KOYORI_BROWSER_RESTART_SEC:-3}"
while true; do
  if koyori_run_browser; then
    log "browser ended normally — restart in ${BROWSER_RESTART_SEC}s"
  else
    log "browser failed — restart in ${BROWSER_RESTART_SEC}s"
  fi
  sleep "$BROWSER_RESTART_SEC"
done
