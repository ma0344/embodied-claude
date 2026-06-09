#!/usr/bin/env bash
# Shared Keychron reconnect helpers (source only).

koyori_keychron_load_config() {
  SLOT=2
  NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-K4 Max}"
  if [[ -f "${HOME}/.config/koyori-keychron" ]]; then
    # shellcheck disable=SC1090
    source "${HOME}/.config/koyori-keychron"
  fi
}

koyori_keychron_is_connected() {
  local mac name
  while read -r _ mac _rest; do
    [[ -z "$mac" ]] && continue
    if bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes'; then
      return 0
    fi
  done < <(bluetoothctl devices 2>/dev/null | grep -i keychron || true)
  return 1
}

koyori_keychron_pick_mac_from_log() {
  local pattern="$1"
  local log="$2"
  local mac=""
  mac=$(grep -iE '\[NEW\] Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}' | tail -1 || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  mac=$(grep -iE '^Device [0-9A-F:]{17}' "$log" | grep -i "$pattern" | tail -1 \
    | awk '{print $2}' || true)
  [[ -n "$mac" ]] && { echo "$mac"; return 0; }
  return 1
}

# Try bonded/paired MACs first, then scan (keyboard must be on Fn+slot).
koyori_keychron_connect() {
  local scan_sec="${1:-20}"
  local log pair_log mac

  koyori_keychron_load_config

  if koyori_keychron_is_connected; then
    echo "already connected"
    return 0
  fi

  log=$(mktemp)
  pair_log=$(mktemp)

  # 1) Reconnect known paired entries (bond survives random MAC rotation).
  while read -r _ mac _rest; do
    [[ -z "$mac" ]] && continue
    if {
      echo power on
      sleep 1
      echo "connect $mac"
      sleep 8
      echo quit
    } | bluetoothctl 2>&1 | tee -a "$log" | grep -qiE 'Connection successful|Connected: yes'; then
      rm -f "$log" "$pair_log"
      echo "connected $mac (paired)"
      return 0
    fi
  done < <(bluetoothctl devices 2>/dev/null | grep -i keychron || true)

  if [[ -n "${LAST_MAC:-}" ]]; then
    if {
      echo power on
      sleep 1
      echo "connect $LAST_MAC"
      sleep 8
      echo quit
    } | bluetoothctl 2>&1 | tee -a "$log" | grep -qiE 'Connection successful|Connected: yes'; then
      rm -f "$log" "$pair_log"
      echo "connected $LAST_MAC (last)"
      return 0
    fi
  fi

  # 2) Scan — user should press Fn+slot on keyboard now.
  {
    echo power on
    sleep 1
    echo agent on
    echo default-agent
    echo scan on
    sleep "$scan_sec"
    echo scan off
    sleep 1
    echo devices
  } | bluetoothctl 2>&1 | tee "$log" || true

  if ! mac=$(koyori_keychron_pick_mac_from_log "$NAME_PATTERN" "$log"); then
    rm -f "$log" "$pair_log"
    return 1
  fi

  {
    echo power on
    echo agent on
    echo default-agent
    echo "trust $mac"
    echo "connect $mac"
    sleep 12
    echo "info $mac"
    echo quit
  } | bluetoothctl 2>&1 | tee "$pair_log" || true

  mkdir -p "${HOME}/.config"
  if [[ -f "${HOME}/.config/koyori-keychron" ]]; then
    sed -i "s/^LAST_MAC=.*/LAST_MAC=$mac/" "${HOME}/.config/koyori-keychron" 2>/dev/null || true
  fi

  if grep -qiE 'Connection successful|Connected: yes' "$pair_log" \
    || bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes'; then
    rm -f "$log" "$pair_log"
    echo "connected $mac (scan)"
    return 0
  fi

  rm -f "$log" "$pair_log"
  return 1
}
