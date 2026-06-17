#!/usr/bin/env bash
# Input Leap client — share ma-home (Windows Server) keyboard/mouse. Source only.

koyori_input_leap_log() {
  echo "$(date -Is) input-leap: $*"
}

koyori_input_leap_wait_server() {
  local server="$1"
  local max_wait="${2:-120}"
  local i=0
  if ! command -v nc >/dev/null 2>&1; then
    return 0
  fi
  while (( i < max_wait )); do
    if nc -z -w 2 "$server" 24800 2>/dev/null; then
      koyori_input_leap_log "server $server:24800 reachable"
      return 0
    fi
    if (( i == 0 )); then
      koyori_input_leap_log "waiting for server $server:24800 (ma-home may still be booting)"
    fi
    sleep 2
    ((i += 2)) || true
  done
  koyori_input_leap_log "WARN server $server:24800 still down — starting client with --restart anyway"
  return 1
}

koyori_input_leap_launch_client() {
  local name="$1"
  local server="$2"
  local profile_dir="$3"
  shift 3
  local -a crypto_flag=("$@")

  input-leapc -f --restart "${crypto_flag[@]}" \
    --profile-dir "$profile_dir" \
    --display "${DISPLAY:-:0}" \
    --name "$name" \
    --debug INFO \
    "$server" &
  koyori_input_leap_log "client name=$name server=$server pid=$! crypto=${KOYORI_INPUT_LEAP_CRYPTO:-0}"
}

koyori_input_leap_start_watch() {
  local server="$1"
  local interval="${KOYORI_INPUT_LEAP_WATCH_INTERVAL:-30}"
  local watch_pid_file="/tmp/koyori-input-leap-watch.$(id -u).pid"
  (
    echo "$$" >"$watch_pid_file"
    trap 'rm -f "$watch_pid_file"' EXIT
    sleep "${KOYORI_INPUT_LEAP_WATCH_DELAY:-30}"
    koyori_input_leap_log "watch start interval=${interval}s"
    while true; do
      if ! pgrep -u "$(id -u)" -f "input-leapc.*${server}" >/dev/null 2>&1; then
        koyori_input_leap_log "watch: client not running — relaunch"
        koyori_input_leap_start_once
      fi
      sleep "$interval"
    done
  ) &
  koyori_input_leap_log "watch pid=$!"
}

koyori_input_leap_start_once() {
  local name server profile_dir trust_src
  name="${KOYORI_INPUT_LEAP_NAME:-koyori}"
  server="${KOYORI_INPUT_LEAP_SERVER}"
  profile_dir="${KOYORI_INPUT_LEAP_PROFILE_DIR:-${HOME}/.local/share/InputLeap}"
  local -a crypto_flag=(--disable-crypto)
  if [[ "${KOYORI_INPUT_LEAP_CRYPTO:-0}" == "1" ]]; then
    crypto_flag=(--enable-crypto)
  fi

  trust_src="${KOYORI_INPUT_LEAP_TRUST_FILE:-/etc/koyori-kiosk/input-leap-server-fingerprint.txt}"
  if [[ "${KOYORI_INPUT_LEAP_CRYPTO:-0}" != "0" ]]; then
    if [[ -f "$trust_src" && -x /usr/local/bin/koyori-input-leap-trust-server ]]; then
      /usr/local/bin/koyori-input-leap-trust-server "$trust_src" >/dev/null 2>&1 || true
    elif [[ ! -f "${profile_dir}/SSL/Fingerprints/TrustedServers.txt" ]]; then
      koyori_input_leap_log "WARN no TrustedServers.txt — see docs/koyori-input-sharing.md"
    fi
  fi

  koyori_input_leap_wait_server "$server" "${KOYORI_INPUT_LEAP_SERVER_WAIT_SEC:-120}" || true
  koyori_input_leap_launch_client "$name" "$server" "$profile_dir" "${crypto_flag[@]}"
}

if [[ -z "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
  koyori_input_leap_log "disabled (set KOYORI_INPUT_LEAP_SERVER in /etc/default/koyori-kiosk)"
  return 0
fi

if ! command -v input-leapc >/dev/null 2>&1; then
  koyori_input_leap_log "WARN input-leapc not installed — see docs/koyori-input-sharing.md"
  return 0
fi

if pgrep -u "$(id -u)" -f "input-leapc.*${KOYORI_INPUT_LEAP_SERVER}" >/dev/null 2>&1; then
  koyori_input_leap_log "already running server=${KOYORI_INPUT_LEAP_SERVER}"
else
  koyori_input_leap_start_once
fi

if [[ "${KOYORI_INPUT_LEAP_WATCH:-1}" == "1" ]]; then
  watch_pid_file="/tmp/koyori-input-leap-watch.$(id -u).pid"
  if [[ -f "$watch_pid_file" ]] && kill -0 "$(cat "$watch_pid_file" 2>/dev/null)" 2>/dev/null; then
    koyori_input_leap_log "watch already running pid=$(cat "$watch_pid_file")"
  else
    koyori_input_leap_start_watch "${KOYORI_INPUT_LEAP_SERVER}"
  fi
fi
