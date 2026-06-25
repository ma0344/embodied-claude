#!/usr/bin/env bash
# One-time IBus dconf scrub for kiosk user (install). Avoids stale mozc-on / xkb engine names.

set -euo pipefail

MA_USER="${1:-ma}"

if ! id "$MA_USER" &>/dev/null; then
  echo "WARN: user $MA_USER not found; skip ibus preseed" >&2
  exit 0
fi

scrub() {
  if ! command -v gsettings >/dev/null 2>&1; then
    return 0
  fi
  local preload order
  preload=$(gsettings get org.freedesktop.ibus.general preload-engines 2>/dev/null || true)
  order=$(gsettings get org.freedesktop.ibus.general engines-order 2>/dev/null || true)
  if [[ "$preload" == *mozc-on* || "$preload" == *mozc-jp-ro* || "$order" == *mozc-on* ]]; then
    gsettings set org.freedesktop.ibus.general preload-engines "[]" 2>/dev/null || true
    gsettings set org.freedesktop.ibus.general engines-order "[]" 2>/dev/null || true
  fi
}

runuser -u "$MA_USER" -- bash -c "$(declare -f scrub); scrub" || scrub || true
echo "  ibus preseed: scrub mozc-on from preload/order if present ($MA_USER)"
