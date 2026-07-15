#!/usr/bin/env bash
# Install koyori near-eye Phase 1: capture binary + JPEG HTTP.
# Refresh timer units are installed but NOT enabled (Surface LED; on-demand /see).
#
# Run on koyori (Surface Go):
#   cd ~/src/embodied-claude/scripts/koyori-kiosk
#   sudo ./install-koyori-near-eye.sh
#
# Verify from ma-home:
#   curl -fsS http://koyori.local:8765/health
#   curl -fsS -o see.jpg http://koyori.local:8765/see
#

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
CAPTURE_SRC="$REPO_ROOT/scripts/koyori-capture.sh"

if [[ ! -f "$CAPTURE_SRC" ]]; then
  echo "ERROR: missing $CAPTURE_SRC" >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_DIR/koyori-see-http.py" ]]; then
  echo "ERROR: missing $SCRIPT_DIR/koyori-see-http.py" >&2
  exit 1
fi

if ! command -v gst-launch-1.0 >/dev/null 2>&1; then
  echo "ERROR: gst-launch-1.0 not found (gstreamer1.0-tools / libcamera)" >&2
  exit 1
fi
if ! id -u ma >/dev/null 2>&1; then
  echo "ERROR: user ma not found" >&2
  exit 1
fi
if ! id -nG ma | tr ' ' '\n' | grep -qx video; then
  echo "WARN: user ma is not in group video — capture may fail" >&2
fi

install -d -m 755 -o ma -g video /var/lib/koyori
install -m 755 "$CAPTURE_SRC" /usr/local/bin/koyori-capture
install -m 755 "$SCRIPT_DIR/koyori-see-http.py" /usr/local/bin/koyori-see-http
install -m 644 "$SCRIPT_DIR/koyori-see-http.service" /etc/systemd/system/koyori-see-http.service
install -m 644 "$SCRIPT_DIR/koyori-capture-refresh.service" /etc/systemd/system/koyori-capture-refresh.service
install -m 644 "$SCRIPT_DIR/koyori-capture-refresh.timer" /etc/systemd/system/koyori-capture-refresh.timer

if [[ ! -f /etc/default/koyori-see ]]; then
  cat >/etc/default/koyori-see <<'EOF'
# Optional overrides for koyori near-eye (sourced by systemd units).
# KOYORI_SEE_HOST=0.0.0.0
# KOYORI_SEE_PORT=8765
# KOYORI_PICK_FRAME=12
# KOYORI_CAPTURE_TIMEOUT=18
EOF
  chmod 644 /etc/default/koyori-see
fi

systemctl daemon-reload
systemctl enable --now koyori-see-http.service
# Policy B': do not enable periodic capture (camera LED). Units remain for optional use.
systemctl disable --now koyori-capture-refresh.timer 2>/dev/null || true
# Seed latest.jpg once so /latest.jpg is not empty until first /see
systemctl start koyori-capture-refresh.service || true

echo "Installed near-eye Phase 1 (refresh timer disabled by default)."
echo "  curl -fsS http://127.0.0.1:8765/health"
echo "  curl -fsS -o see.jpg http://127.0.0.1:8765/see"
echo "  systemctl status koyori-see-http.service --no-pager"
echo "  # optional periodic refresh: systemctl enable --now koyori-capture-refresh.timer"
