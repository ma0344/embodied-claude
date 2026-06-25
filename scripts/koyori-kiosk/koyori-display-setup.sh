#!/usr/bin/env bash
# Configure X display for kiosk fullscreen. Source from koyori-kiosk.sh (do not exec).

koyori_display_log() {
  echo "$(date -Is) display: $*"
}

koyori_display_log "start DISPLAY=${DISPLAY:-unset}"

if command -v xsetroot >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  xsetroot -solid "#f5f5f0" || true
fi

if command -v xrandr >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  primary=""
  while read -r output _rest; do
    [[ -z "$output" ]] && continue
    xrandr --output "$output" --auto 2>/dev/null || true
    [[ -z "$primary" ]] && primary="$output"
  done < <(xrandr | awk '/ connected/{print $1}')

  if [[ -n "$primary" ]]; then
    xrandr --output "$primary" --primary 2>/dev/null || true
    if [[ -n "${KOYORI_DISPLAY_MODE:-}" ]]; then
      if xrandr --output "$primary" --mode "$KOYORI_DISPLAY_MODE" 2>/dev/null; then
        koyori_display_log "mode=$KOYORI_DISPLAY_MODE output=$primary"
      else
        koyori_display_log "WARN could not set mode $KOYORI_DISPLAY_MODE on $primary"
      fi
    fi
    koyori_display_log "primary=$primary current=$(xrandr | awk -v o="$primary" '$1==o{print; getline; print}' | tr '\n' ' ')"
  else
    koyori_display_log "WARN no connected outputs in xrandr"
  fi
else
  koyori_display_log "WARN xrandr unavailable"
fi

if command -v xdpyinfo >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  dims=$(xdpyinfo | awk '/dimensions:/{print $2; exit}')
  if [[ -n "$dims" ]]; then
    export KOYORI_SCREEN_W="${dims%x*}"
    export KOYORI_SCREEN_H="${dims#*x}"
    koyori_display_log "dimensions=${KOYORI_SCREEN_W}x${KOYORI_SCREEN_H}"
  fi
fi

koyori_start_window_manager() {
  if [[ "${KOYORI_USE_WM:-1}" != "1" ]]; then
    return 0
  fi
  if command -v openbox >/dev/null 2>&1; then
    openbox --sm-disable &
    sleep 0.3
    if [[ -f "${HOME}/.config/openbox/rc.xml" ]]; then
      openbox --reconfigure 2>/dev/null || true
    fi
    koyori_display_log "wm=openbox"
    return 0
  fi
  koyori_display_log "WARN openbox not installed (apt install openbox)"
}

# Resize browser windows to root size (Firefox snap + --kiosk often maps 1x1 helper windows).
koyori_window_geometry() {
  local wid="$1"
  local x y width height
  if command -v xwininfo >/dev/null 2>&1; then
    local info
    info=$(xwininfo -id "$wid" 2>/dev/null || true)
    if [[ -n "$info" ]]; then
      width=$(awk '/Width:/{print $2; exit}' <<<"$info")
      height=$(awk '/Height:/{print $2; exit}' <<<"$info")
      x=$(awk '/Absolute upper-left X:/{print $4; exit}' <<<"$info")
      y=$(awk '/Absolute upper-left Y:/{print $4; exit}' <<<"$info")
      echo "${x:-0} ${y:-0} ${width:-0} ${height:-0}"
      return 0
    fi
  fi
  eval "$(xdotool getwindowgeometry --shell "$wid" 2>/dev/null || true)"
  echo "${X:-0} ${Y:-0} ${WIDTH:-0} ${HEIGHT:-0}"
}

koyori_collect_browser_window_ids() {
  local browser_pid="${1:-}"
  local -a ids=()
  local wid cls

  # Navigator is the real Firefox toplevel on X11; plain "Firefox" class may be 1x1 chrome.
  for cls in Navigator Firefox firefox; do
    while read -r wid; do
      [[ -n "$wid" ]] && ids+=("$wid")
    done < <(xdotool search --class "$cls" 2>/dev/null || true)
  done

  if [[ -n "$browser_pid" ]] && kill -0 "$browser_pid" 2>/dev/null; then
    while read -r wid; do
      [[ -n "$wid" ]] && ids+=("$wid")
    done < <(xdotool search --pid "$browser_pid" 2>/dev/null || true)
  fi

  if ((${#ids[@]} == 0)); then
    return 0
  fi

  printf '%s\n' "${ids[@]}" | awk '!seen[$0]++'
}

koyori_firefox_request_fullscreen() {
  local wid="$1"
  command -v xdotool >/dev/null 2>&1 || return 0
  xdotool windowactivate --sync "$wid" 2>/dev/null || xdotool windowactivate "$wid" 2>/dev/null || true
  sleep 0.25
  xdotool key --window "$wid" F11 2>/dev/null || xdotool key F11 2>/dev/null || true
}

koyori_raise_browser_window() {
  local wid="$1"
  local w="${KOYORI_SCREEN_W:-}"
  local h="${KOYORI_SCREEN_H:-}"
  local name=""
  command -v xdotool >/dev/null 2>&1 || return 0
  [[ -n "$wid" ]] || return 0

  name=$(xdotool getwindowname "$wid" 2>/dev/null || echo "")
  xdotool windowmap "$wid" 2>/dev/null || true
  xdotool windowactivate "$wid" 2>/dev/null || true
  xdotool windowraise "$wid" 2>/dev/null || true
  if [[ -n "$w" && -n "$h" ]]; then
    xdotool windowmove --sync "$wid" 0 0 2>/dev/null || xdotool windowmove "$wid" 0 0 2>/dev/null || true
    xdotool windowsize --sync "$wid" "$w" "$h" 2>/dev/null || xdotool windowsize "$wid" "$w" "$h" 2>/dev/null || true
  fi
  if command -v wmctrl >/dev/null 2>&1; then
    wmctrl -i -r "$wid" -b add,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true
    if [[ -n "$name" ]]; then
      wmctrl -F -r "$name" -b add,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true
      wmctrl -F -r "$name" -e "0,0,0,${w:-1800},${h:-1200}" 2>/dev/null || true
    fi
  fi
}

koyori_resize_browser_window() {
  local browser_pid="${1:-}"
  local w="${KOYORI_SCREEN_W:-}"
  local h="${KOYORI_SCREEN_H:-}"
  local min_dim="${KOYORI_BROWSER_MIN_DIM:-200}"

  [[ -n "$w" && -n "$h" ]] || return 0
  command -v xdotool >/dev/null 2>&1 || {
    koyori_display_log "WARN xdotool missing — skip window resize"
    return 0
  }

  local -a window_ids=()
  local i wid x y width height area best_wid best_area name score best_score
  best_wid=""
  best_area=0
  best_score=-1

  for i in $(seq 1 80); do
    mapfile -t window_ids < <(koyori_collect_browser_window_ids "$browser_pid")
    ((${#window_ids[@]} > 0)) && break
    sleep 0.25
  done

  if ((${#window_ids[@]} == 0)); then
    koyori_display_log "WARN no browser windows found for resize"
    return 0
  fi

  for wid in "${window_ids[@]}"; do
    read -r x y width height < <(koyori_window_geometry "$wid")
    name=$(xdotool getwindowname "$wid" 2>/dev/null || echo "")
    area=$((width * height))
    score=0
    [[ "$name" == *Mozilla* || "$name" == *こより* ]] && score=$((score + 100))
    [[ "$name" == Firefox ]] && score=$((score + 10))
    (( area > min_dim )) && score=$((score + 50))

    if (( width < min_dim || height < min_dim )); then
      koyori_raise_browser_window "$wid"
      read -r x y width height < <(koyori_window_geometry "$wid")
      area=$((width * height))
      koyori_display_log "expanded small window=$wid name=${name:-?} -> ${width}x${height}"
    fi

    if (( score > best_score || (score == best_score && area > best_area) )); then
      best_score=$score
      best_area=$area
      best_wid=$wid
    fi
  done

  for wid in "${window_ids[@]}"; do
    koyori_raise_browser_window "$wid"
  done

  if [[ -n "$best_wid" ]]; then
    koyori_raise_browser_window "$best_wid"
    read -r x y width height < <(koyori_window_geometry "$best_wid")
    if (( width < min_dim || height < min_dim )); then
      koyori_display_log "WARN still small after resize window=$best_wid — sending F11"
      koyori_firefox_request_fullscreen "$best_wid"
      sleep 0.5
      for wid in "${window_ids[@]}"; do
        koyori_firefox_request_fullscreen "$wid"
      done
      read -r x y width height < <(koyori_window_geometry "$best_wid")
    fi
    koyori_display_log "browser primary=$best_wid geometry=${width}x${height}+${x}+${y} target=${w}x${h} windows=${#window_ids[@]}"
  fi
}
