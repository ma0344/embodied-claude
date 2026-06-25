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
  gsettings set org.freedesktop.ibus.general preload-engines "[]" 2>/dev/null || true
  gsettings set org.freedesktop.ibus.general engines-order "[]" 2>/dev/null || true
}

runuser -u "$MA_USER" -- bash -c "$(declare -f scrub); scrub" || scrub || true
echo "  ibus preseed: cleared preload-engines / engines-order for $MA_USER"
