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
export MOZ_ENABLE_WAYLAND=0
export GDK_BACKEND=x11

if ! dpkg -s ibus-mozc >/dev/null 2>&1; then
  koyori_ime_log "ERROR ibus-mozc not installed — run: sudo apt install -y ibus-mozc ibus-gtk3"
  return 0
fi

if ! command -v ibus-daemon >/dev/null 2>&1; then
  koyori_ime_log "ERROR ibus-daemon not found"
  return 0
fi

if [[ -z "${DISPLAY:-}" ]]; then
  koyori_ime_log "WARN DISPLAY unset — IME may not attach to the browser"
fi

koyori_ime_list_engines() {
  ibus list-engine 2>&1
}

koyori_ime_has_mozc() {
  koyori_ime_list_engines | grep -qE '(^|[[:space:]])mozc'
}

koyori_ime_wait_mozc() {
  local seconds="${1:-45}"
  local i=0
  local max=$((seconds * 10))
  while (( i < max )); do
    if koyori_ime_has_mozc; then
      return 0
    fi
    sleep 0.1
    ((i++)) || true
  done
  return 1
}

koyori_ime_activate() {
  local engine current
  for engine in mozc-jp mozc-jp-ro mozc-jp-typing mozc-jp-dv mozc-on mozc; do
    if ibus engine "$engine" 2>/dev/null; then
      current=$(ibus engine 2>/dev/null || echo "$engine")
      koyori_ime_log "engine=$current"
      return 0
    fi
  done
  if koyori_ime_has_mozc; then
    engine=$(koyori_ime_list_engines | awk '/mozc/ {print $1; exit}')
    if [[ -n "$engine" ]] && ibus engine "$engine" 2>/dev/null; then
      current=$(ibus engine 2>/dev/null || echo "$engine")
      koyori_ime_log "engine=$current"
      return 0
    fi
  fi
  return 1
}

koyori_ime_bootstrap() {
  if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
    koyori_ime_log "starting ibus-daemon"
    ibus-daemon -drx --xim &
  fi

  if koyori_ime_wait_mozc 20 && koyori_ime_activate; then
    return 0
  fi

  koyori_ime_log "mozc not ready — restarting ibus-daemon once"
  ibus exit 2>/dev/null || true
  sleep 1
  ibus-daemon -drx --xim &

  if koyori_ime_wait_mozc 45 && koyori_ime_activate; then
    return 0
  fi

  koyori_ime_log "WARN mozc still unavailable after ibus restart"
  koyori_ime_log "engines: $(koyori_ime_list_engines | tr '\n' ' ')"
  return 1
}

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.freedesktop.ibus.general preload-engines "['mozc-jp']" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general engines-order "['mozc-jp']" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general use-global-engine true 2>/dev/null || true
fi

if koyori_ime_bootstrap; then
  return 0
fi

koyori_ime_log "background wait for mozc-jp (up to 60s)"
(
  for _ in $(seq 1 120); do
    sleep 0.5
    if koyori_ime_activate; then
      koyori_ime_log "background engine ok"
      exit 0
    fi
  done
  koyori_ime_log "background timeout — try Ctrl+Space in the input field"
) &
