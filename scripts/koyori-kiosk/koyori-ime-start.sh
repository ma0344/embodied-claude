#!/usr/bin/env bash
# Start IBus + Mozc for koyori kiosk. Source from koyori-kiosk.sh (do not exec).
# Requires: ibus-mozc

koyori_ime_log() {
  echo "$(date -Is) ime: $*"
}

export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export CLUTTER_IM_MODULE=ibus
export SDL_IM_MODULE=ibus

if ! command -v ibus-daemon >/dev/null 2>&1; then
  koyori_ime_log "WARN ibus-daemon not found (install ibus-mozc)"
  return 0
fi

if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
  ibus-daemon -drx &
  ready=0
  for _ in $(seq 1 50); do
    if ibus list-engine >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.1
  done
  if [[ "$ready" -ne 1 ]]; then
    koyori_ime_log "WARN ibus-daemon started but list-engine not ready"
  fi
fi

for engine in mozc-jp mozc-on mozc; do
  if ibus engine "$engine" 2>/dev/null; then
    koyori_ime_log "engine=$engine"
    return 0
  fi
done

if ibus list-engine 2>/dev/null | grep -qi mozc; then
  first=$(ibus list-engine 2>/dev/null | awk '/mozc/ {print $1; exit}')
  if [[ -n "$first" ]] && ibus engine "$first" 2>/dev/null; then
    koyori_ime_log "engine=$first"
    return 0
  fi
fi

koyori_ime_log "WARN no mozc engine found (ibus list-engine)"
