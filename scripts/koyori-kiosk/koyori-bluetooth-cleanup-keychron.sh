#!/usr/bin/env bash
# Remove duplicate Keychron pairings (MAC changed each attempt). Run as root.
#
# Usage: sudo koyori-bluetooth-cleanup-keychron.sh

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "sudo $0" >&2
  exit 1
fi

NAME_PATTERN="${KOYORI_KEYCHRON_NAME:-Keychron}"

echo "Removing bonded Keychron devices matching *${NAME_PATTERN}* ..."
while read -r _ mac _rest; do
  [[ -n "$mac" ]] || continue
  echo "  remove $mac"
  bluetoothctl remove "$mac" 2>/dev/null || true
done < <(bluetoothctl devices 2>/dev/null | grep -i "$NAME_PATTERN" || true)

systemctl restart bluetooth
echo "Done. Re-pair: koyori-pair-keychron.sh 2"
