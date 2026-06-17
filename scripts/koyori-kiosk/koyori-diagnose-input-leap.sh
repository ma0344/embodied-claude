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
echo "    KOYORI_INPUT_LEAP_CRYPTO=${KOYORI_INPUT_LEAP_CRYPTO:-0}"

echo ""
if command -v input-leapc >/dev/null 2>&1; then
  echo "  input-leapc: $(command -v input-leapc)"
  MISSING_LIBS=$(ldd "$(command -v input-leapc)" 2>/dev/null | grep 'not found' || true)
  if [[ -n "$MISSING_LIBS" ]]; then
    echo "  input-leapc libs: BROKEN"
    echo "$MISSING_LIBS" | sed 's/^/    /'
    echo "    fix: sudo apt-get install -y libei1 libportal1"
    echo "         sudo ./install-input-leap-tarball.sh  # re-run after apt"
  elif /usr/local/bin/input-leapc --help >/dev/null 2>&1; then
    echo "  input-leapc libs: ok"
  else
    echo "  input-leapc libs: unknown (run: input-leapc --help)"
  fi
else
  echo "  input-leapc: MISSING — sudo ./install-input-leap-tarball.sh"
fi

echo ""
if [[ -z "${KOYORI_INPUT_LEAP_SERVER:-}" ]]; then
  echo "  status: disabled — set KOYORI_INPUT_LEAP_SERVER in /etc/default/koyori-kiosk"
else
  if pgrep -af input-leapc 2>/dev/null | grep -v diagnose; then
    echo "  status: client process running"
  else
    echo "  status: client NOT running"
    echo "    fix: grep input-leap /tmp/koyori-kiosk.log | tail -20"
    echo "         sudo reboot  (or wait for watch to relaunch)"
  fi
  if command -v nc >/dev/null 2>&1; then
    if nc -z -w 2 "$KOYORI_INPUT_LEAP_SERVER" 24800 2>/dev/null; then
      echo "  tcp 24800: reachable on $KOYORI_INPUT_LEAP_SERVER"
    else
      echo "  tcp 24800: NOT reachable on $KOYORI_INPUT_LEAP_SERVER (firewall / Server stopped?)"
    fi
  fi
  profile_dir="${KOYORI_INPUT_LEAP_PROFILE_DIR:-${HOME}/.local/share/InputLeap}"
  trusted="${profile_dir}/SSL/Fingerprints/TrustedServers.txt"
  echo ""
  if [[ "${KOYORI_INPUT_LEAP_CRYPTO:-0}" == "0" ]]; then
    echo "  ssl trust: disabled (KOYORI_INPUT_LEAP_CRYPTO=0)"
  elif [[ -f "$trusted" ]]; then
    echo "  ssl trust: $trusted ($(wc -l <"$trusted") line(s))"
  else
    echo "  ssl trust: MISSING — copy ma-home Local.txt:"
    echo "    koyori-input-leap-trust-server -   # paste v2:sha* lines"
  fi
fi

echo ""
echo "  recent errors (kiosk log):"
if [[ -f /tmp/koyori-kiosk.log ]]; then
  grep -E 'ERROR|FATAL|fingerprint|TrustedServers|SecureSocket' /tmp/koyori-kiosk.log 2>/dev/null | tail -8 | sed 's/^/    /' \
    || echo "    (none — check full log if still failing)"
else
  echo "    /tmp/koyori-kiosk.log missing"
fi

echo ""
echo "  recent input-leap log:"
if [[ -f /tmp/koyori-kiosk.log ]]; then
  grep input-leap /tmp/koyori-kiosk.log | tail -5 | sed 's/^/    /' || echo "    (no input-leap lines)"
else
  echo "    /tmp/koyori-kiosk.log missing"
fi

echo ""
echo "  docs: docs/koyori-input-sharing.md"
