#!/usr/bin/env bash
# Diagnose Input Leap client on koyori (SSH ok; kiosk session on :0).

set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"

echo "=== Input Leap (koyori client) ==="
echo "    DISPLAY=$DISPLAY user=$USER"

if [[ -f /etc/default/koyori-kiosk ]]; then
  # shellcheck disable=SC1091
  source /etc/default/koyori-kiosk
fi

echo ""
echo "  config:"
echo "    KOYORI_INPUT_LEAP_SERVER=${KOYORI_INPUT_LEAP_SERVER:-(unset)}"
echo "    KOYORI_INPUT_LEAP_NAME=${KOYORI_INPUT_LEAP_NAME:-koyori}"
echo "    KOYORI_INPUT_LEAP_CRYPTO=${KOYORI_INPUT_LEAP_CRYPTO:-1}"

echo ""
if command -v input-leapc >/dev/null 2>&1; then
  echo "  input-leapc: $(command -v input-leapc)"
else
  echo "  input-leapc: MISSING — install .deb from GitHub releases"
fi

echo ""
if [[ -z "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
  echo "  status: disabled — set KOYORI_INPUT_LEAP_SERVER in /etc/default/koyori-kiosk"
else
  if pgrep -af input-leapc 2>/dev/null | grep -v diagnose; then
    echo "  status: client process running"
  else
    echo "  status: client NOT running (reboot or check /tmp/koyori-kiosk.log)"
  fi
  if command -v nc >/dev/null 2>&1; then
    if nc -z -w 2 "$KOYORI_INPUT_LEAP_SERVER" 24800 2>/dev/null; then
      echo "  tcp 24800: reachable on $KOYORI_INPUT_LEAP_SERVER"
    else
      echo "  tcp 24800: NOT reachable on $KOYORI_INPUT_LEAP_SERVER (firewall / Server stopped?)"
    fi
  fi
fi

echo ""
echo "  recent kiosk log:"
if [[ -f /tmp/koyori-kiosk.log ]]; then
  grep input-leap /tmp/koyori-kiosk.log | tail -10 | sed 's/^/    /' || echo "    (no input-leap lines)"
else
  echo "    /tmp/koyori-kiosk.log missing"
fi

echo ""
echo "  docs: docs/koyori-input-sharing.md"
