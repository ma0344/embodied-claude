#!/usr/bin/env bash
# Start IBus + Mozc for koyori kiosk. Source from koyori-kiosk.sh (do not exec).
# Requires: ibus-mozc ibus-gtk3

koyori_ime_log() {
  echo "$(date -Is) ime: $*"
}

koyori_ime_log "start DISPLAY=${DISPLAY:-unset} uid=$(id -u)"

export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export CLUTTER_IM_MODULE=ibus
export SDL_IM_MODULE=ibus

if ! dpkg -s ibus-mozc >/dev/null 2>&1; then
  koyori_ime_log "ERROR ibus-mozc not installed — run: sudo apt install -y ibus-mozc ibus-gtk3"
  return 0
fi

if ! command -v ibus-daemon >/dev/null 2>&1; then
  koyori_ime_log "ERROR ibus-daemon not found"
  return 0
fi

if [[ -z "${DISPLAY:-}" ]]; then
  koyori_ime_log "WARN DISPLAY unset — IME may not attach to Chromium"
fi

_ime_list_engines() {
  ibus list-engine 2>&1
}

_ime_has_mozc() {
  _ime_list_engines | grep -qi mozc
}

if pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1 && ! _ime_has_mozc; then
  koyori_ime_log "ibus running without mozc — restarting ibus-daemon"
  ibus exit 2>/dev/null || true
  sleep 0.5
fi

if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
  ibus-daemon -drx &
  ready=0
  for _ in $(seq 1 80); do
    if _ime_has_mozc; then
      ready=1
      break
    fi
    sleep 0.1
  done
  if [[ "$ready" -ne 1 ]]; then
    koyori_ime_log "WARN mozc not registered after ibus-daemon start"
    koyori_ime_log "engines: $(_ime_list_engines | tr '\n' ' ')"
  fi
fi

for engine in mozc-jp mozc-jp-ro mozc-jp-typing mozc-jp-dv mozc-on mozc; do
  if ibus engine "$engine" 2>/dev/null; then
    koyori_ime_log "engine=$engine"
    return 0
  fi
done

if _ime_has_mozc; then
  first=$(_ime_list_engines | awk '/mozc/ {print $1; exit}')
  if [[ -n "$first" ]] && ibus engine "$first" 2>/dev/null; then
    koyori_ime_log "engine=$first"
    return 0
  fi
fi

koyori_ime_log "WARN no mozc engine found"
koyori_ime_log "engines: $(_ime_list_engines | tr '\n' ' ')"
