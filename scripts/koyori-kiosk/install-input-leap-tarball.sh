#!/usr/bin/env bash
# Install Input Leap client binaries from GitHub release tarball (no .deb).
#
# Usage (on koyori):
#   sudo ./install-input-leap-tarball.sh
#   sudo ./install-input-leap-tarball.sh /tmp/input-leap-ubuntu-24-04-v3.0.3.tar.gz
#
# v3.0.3 tarballs nest a second .tar.gz that is actually plain tar — this script handles that.

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0 [path-to.tar.gz]" >&2
  exit 1
fi

TARBALL="${1:-/tmp/input-leap-ubuntu-24-04-v3.0.3.tar.gz}"
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

if [[ ! -f "$TARBALL" ]]; then
  echo "ERROR: not found: $TARBALL" >&2
  exit 1
fi

echo "Extracting $TARBALL ..."
tar -xzf "$TARBALL" -C "$WORKDIR"

ROOT=$(find "$WORKDIR" -mindepth 1 -maxdepth 1 -type d | head -1)
if [[ -z "$ROOT" ]]; then
  echo "ERROR: empty tarball" >&2
  exit 1
fi

INNER=$(find "$ROOT" -maxdepth 1 -name '*.tar.gz' -type f | head -1)
if [[ -n "$INNER" ]]; then
  echo "Extracting nested archive $(basename "$INNER") ..."
  tar -xf "$INNER" -C "$ROOT"
fi

# Layout: .../input-leap-ubuntu-24-04/bin/input-leapc
BINDIR=$(find "$ROOT" -type f -name input-leapc -printf '%h\n' 2>/dev/null | head -1)
if [[ -z "$BINDIR" ]]; then
  BINDIR=$(find "$ROOT" -type d -name bin -print 2>/dev/null | head -1)
fi
if [[ -z "$BINDIR" || ! -x "$BINDIR/input-leapc" ]]; then
  echo "ERROR: input-leapc not found under $ROOT" >&2
  find "$ROOT" -type f 2>/dev/null | head -20
  exit 1
fi

PKGROOT=$(dirname "$BINDIR")
echo "Installing from $PKGROOT"

install -m 755 "$BINDIR/input-leapc" /usr/local/bin/input-leapc
if [[ -x "$BINDIR/input-leaps" ]]; then
  install -m 755 "$BINDIR/input-leaps" /usr/local/bin/input-leaps
fi
if [[ -x "$BINDIR/input-leap" ]]; then
  install -m 755 "$BINDIR/input-leap" /usr/local/bin/input-leap
fi

if [[ -d "$PKGROOT/share" ]]; then
  cp -a "$PKGROOT/share/." /usr/local/share/
fi

# Qt6 runtime (GUI optional; CLI client needs libs)
MISSING=()
for lib in libQt6Core.so.6 libssl.so.3 libcrypto.so.3; do
  if ! ldconfig -p 2>/dev/null | grep -q "$lib"; then
    MISSING+=("$lib")
  fi
done
if ((${#MISSING[@]})); then
  echo "Installing Qt6 / SSL runtime packages ..."
  apt-get update
  apt-get install -y libqt6core6t64 libqt6gui6t64 libqt6widgets6t64 libssl3t64 2>/dev/null \
    || apt-get install -y libqt6core6 libqt6gui6 libqt6widgets6 libssl3
fi

echo ""
echo "Installed:"
/usr/local/bin/input-leapc --help 2>&1 | head -3 || true
echo ""
echo "Next:"
echo "  1. Set KOYORI_INPUT_LEAP_SERVER in /etc/default/koyori-kiosk"
echo "  2. sudo reboot  (or restart kiosk session)"
echo "  3. koyori-diagnose-input-leap"
