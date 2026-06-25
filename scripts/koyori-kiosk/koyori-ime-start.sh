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

xkb_layout="${KOYORI_XKB_LAYOUT:-}"
if [[ -z "$xkb_layout" && -n "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
  xkb_layout=jp
fi
if [[ -n "$xkb_layout" ]] && command -v setxkbmap >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  if setxkbmap -layout "$xkb_layout" 2>/dev/null; then
    koyori_ime_log "xkb layout=$xkb_layout"
  else
    koyori_ime_log "WARN setxkbmap layout=$xkb_layout failed"
  fi
fi

mozc_config_dir="${HOME}/.config/mozc"
koyori_ime_install_mozc_configs() {
  install -d -m 700 "$mozc_config_dir"
  if [[ -f /usr/local/share/koyori-kiosk/mozc-kiosk-config.textproto ]]; then
    if [[ ! -f "${mozc_config_dir}/config.textproto" ]]; then
      cp /usr/local/share/koyori-kiosk/mozc-kiosk-config.textproto "${mozc_config_dir}/config.textproto"
      koyori_ime_log "installed mozc config.textproto (ROMAN / MS-IME)"
    fi
  fi
  # Input Leap or KOYORI_MOZC_ALWAYS_JP=1: hiragana on launch (no hotkey toggle).
  if [[ -n "${KOYORI_INPUT_LEAP_SERVER:-}" || "${KOYORI_MOZC_ALWAYS_JP:-0}" == "1" ]]; then
    if [[ -f /usr/local/share/koyori-kiosk/mozc-ibus-kiosk.textproto ]]; then
      cp /usr/local/share/koyori-kiosk/mozc-ibus-kiosk.textproto "${mozc_config_dir}/ibus_config.textproto"
      koyori_ime_log "ibus_config: active_on_launch + HIRAGANA (Input Leap / always-jp)"
    fi
  elif [[ -f /usr/local/share/koyori-kiosk/mozc-ibus-kiosk.textproto && ! -f "${mozc_config_dir}/ibus_config.textproto" ]]; then
    cp /usr/local/share/koyori-kiosk/mozc-ibus-kiosk.textproto "${mozc_config_dir}/ibus_config.textproto"
    koyori_ime_log "installed default ibus_config.textproto"
  fi
}
koyori_ime_install_mozc_configs

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

koyori_ime_all_engine_ids() {
  koyori_ime_list_engines | awk '/^  / { print $1 }'
}

# Engine IDs from `ibus list-engine` (e.g. mozc-jp). Not Mozc textproto names (mozc-on).
koyori_ime_mozc_engine_ids() {
  koyori_ime_list_engines | awk '/mozc/ { print $1 }' | sort -u
}

koyori_ime_has_mozc() {
  koyori_ime_mozc_engine_ids | grep -q .
}

koyori_ime_gsettings_engine_array() {
  local -a ids=()
  local id
  while IFS= read -r id; do
    [[ -n "$id" ]] && ids+=("$id")
  done < <(koyori_ime_mozc_engine_ids)
  if ((${#ids[@]} == 0)); then
    echo "['mozc-jp']"
    return 0
  fi
  local quoted="" first=1
  for id in "${ids[@]}"; do
    if (( first )); then
      quoted="'${id}'"
      first=0
    else
      quoted+=", '${id}'"
    fi
  done
  echo "[${quoted}]"
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
  local -a engines=()
  while IFS= read -r engine; do
    [[ -n "$engine" ]] && engines+=("$engine")
  done < <(koyori_ime_mozc_engine_ids)
  if ((${#engines[@]} == 0)); then
    return 1
  fi
  for engine in "${engines[@]}"; do
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

koyori_ime_apply_gsettings() {
  local engines_array
  if ! command -v gsettings >/dev/null 2>&1; then
    return 0
  fi
  engines_array=$(koyori_ime_gsettings_engine_array)
  koyori_ime_log "gsettings engines=$engines_array"
  gsettings set org.freedesktop.ibus.general preload-engines "$engines_array" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general engines-order "$engines_array" 2>/dev/null || true
  if [[ -n "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
    # 1 = show panel always (ibus-setup: Show property panel → Always)
    gsettings set org.freedesktop.ibus.panel show 1 2>/dev/null || true
  fi
  gsettings set org.freedesktop.ibus.general use-global-engine true 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general.hotkey triggers "['Control+space', 'Zenkaku_Hankaku', 'Hangul']" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general use-system-keyboard-layout false 2>/dev/null || true
}

koyori_ime_scrub_gsettings_bootstrap() {
  # Empty preload until engines exist — avoids dialog for mozc-on (missing) or mozc-jp (not registered yet).
  if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.freedesktop.ibus.general preload-engines "[]" 2>/dev/null || true
    gsettings set org.freedesktop.ibus.general engines-order "[]" 2>/dev/null || true
  fi
}

koyori_ime_stop_daemon() {
  if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
    return 0
  fi
  koyori_ime_log "stopping existing ibus-daemon (stale engine config)"
  if command -v ibus >/dev/null 2>&1; then
    ibus exit 2>/dev/null || true
  fi
  sleep 1
  if pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
    pkill -u "$(id -u)" -x ibus-daemon 2>/dev/null || true
    sleep 0.5
  fi
}

koyori_ime_scrub_gsettings_bootstrap
koyori_ime_stop_daemon

if ! pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1; then
  koyori_ime_log "starting ibus-daemon"
  ibus-daemon -drx --xim &
  sleep 2
fi

if koyori_ime_wait_mozc 60; then
  koyori_ime_apply_gsettings
  if command -v ibus >/dev/null 2>&1; then
    ibus write-cache 2>/dev/null || true
  fi
  attempt=0
  while (( attempt < 5 )); do
    if koyori_ime_try_activate; then
      if [[ -n "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
        koyori_ime_log "Input Leap: Mozc toggle Ctrl+Shift+Space (or IBUS panel あ/A)"
      else
        koyori_ime_log "toggle: 半/全; romaji input (konnichiwa)"
      fi
      return 0
    fi
    sleep 1
    ((attempt++)) || true
  done
  koyori_ime_log "mozc registered; manual: koyori-mozc-on; Input Leap needs mozc-ibus-kiosk.textproto"
  return 0
fi

koyori_ime_log "WARN mozc not in ibus list-engine after 60s"
koyori_ime_log "engines: $(koyori_ime_list_engines | tr '\n' ' ')"
