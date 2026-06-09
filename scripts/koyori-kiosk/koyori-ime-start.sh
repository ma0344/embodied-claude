#!/usr/bin/env bash
# Start IBus + Mozc for koyori kiosk. Source from koyori-kiosk.sh (do not exec).
# Requires: ibus-mozc ibus-gtk3
#
# Toggle in Firefox: JIS 半/全 key (Hankaku/Zenkaku). Ctrl+Space is often unbound
# in minimal X sessions.

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

koyori_ime_list_engines() {
  ibus list-engine 2>&1
}

koyori_ime_has_mozc() {
  koyori_ime_list_engines | grep -qE '(^|[[:space:]])mozc'
}

koyori_ime_wait_mozc() {
  local seconds="${1:-60}"
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

koyori_ime_try_activate() {
  local engine err current
  for engine in mozc-jp mozc-jp-ro mozc-on mozc; do
    if err=$(ibus engine "$engine" 2>&1); then
      current=$(ibus engine 2>/dev/null || echo "$engine")
      koyori_ime_log "engine=$current"
      return 0
    fi
    if [[ -n "$err" ]]; then
      koyori_ime_log "engine $engine failed: $err"
    fi
  done
  return 1
}

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.freedesktop.ibus.general preload-engines "['mozc-jp']" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general engines-order "['mozc-jp']" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general use-global-engine true 2>/dev/null || true
fi

if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
  koyori_ime_log "starting ibus-daemon"
  ibus-daemon -drx --xim &
fi

if koyori_ime_wait_mozc 60; then
  if koyori_ime_try_activate; then
    koyori_ime_log "toggle: 半/全 key (JIS) in text fields"
    return 0
  fi
  koyori_ime_log "mozc registered; ibus engine CLI skipped — use 半/全 to toggle"
  return 0
fi

koyori_ime_log "WARN mozc not in ibus list-engine after 60s"
koyori_ime_log "engines: $(koyori_ime_list_engines | tr '\n' ' ')"
