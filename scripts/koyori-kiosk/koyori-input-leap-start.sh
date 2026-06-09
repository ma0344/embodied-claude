#!/usr/bin/env bash
# Input Leap client — share ma-home (Windows Server) keyboard/mouse. Source only.

koyori_input_leap_log() {
  echo "$(date -Is) input-leap: $*"
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
  return 0
fi

name="${KOYORI_INPUT_LEAP_NAME:-koyori}"
server="${KOYORI_INPUT_LEAP_SERVER}"
crypto_flag=(--enable-crypto)
if [[ "${KOYORI_INPUT_LEAP_CRYPTO:-1}" == "0" ]]; then
  crypto_flag=(--disable-crypto)
fi

input-leapc -f "${crypto_flag[@]}" --display "${DISPLAY:-:0}" --name "$name" --debug INFO "$server" &
koyori_input_leap_log "client name=$name server=$server pid=$!"
