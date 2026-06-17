#!/usr/bin/env bash
# Install ma-home Input Leap server fingerprint for the kiosk user (SSL trust).
#
# Usage:
#   koyori-input-leap-trust-server /path/to/Local.txt
#   koyori-input-leap-trust-server v2:sha256:abc...
#   cat Local.txt | koyori-input-leap-trust-server -
#
# ma-home (PowerShell):
#   Get-Content "$env:LOCALAPPDATA\InputLeap\SSL\Fingerprints\Local.txt"

set -euo pipefail

profile_dir="${KOYORI_INPUT_LEAP_PROFILE_DIR:-${HOME}/.local/share/InputLeap}"
fingerprints_dir="${profile_dir}/SSL/Fingerprints"
trusted="${fingerprints_dir}/TrustedServers.txt"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <Local.txt|fingerprint-line|->" >&2
  exit 1
fi

mkdir -p "$fingerprints_dir"

src="$1"
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

if [[ "$src" == "-" ]]; then
  cat >"$tmp"
elif [[ -f "$src" ]]; then
  grep -E '^v2:(sha1|sha256):' "$src" >"$tmp" || true
else
  printf '%s\n' "$src" | grep -E '^v2:(sha1|sha256):' >"$tmp" || true
fi

if [[ ! -s "$tmp" ]]; then
  echo "ERROR: no v2:sha1/sha256 fingerprint lines found" >&2
  exit 1
fi

{
  if [[ -f "$trusted" ]]; then
    grep -E '^v2:(sha1|sha256):' "$trusted" || true
  fi
  cat "$tmp"
} | awk '!seen[$0]++' >"${trusted}.new"
mv "${trusted}.new" "$trusted"
chmod 600 "$trusted"

echo "TrustedServers: $trusted"
cat "$trusted"
