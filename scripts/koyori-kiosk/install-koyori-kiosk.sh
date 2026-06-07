#!/usr/bin/env bash
# Install lightdm autologin + Chromium kiosk session on koyori (Surface Go).
#
# Run on koyori after:
#   sudo apt install -y xorg lightdm chromium-browser unclutter iptsd
#
# Usage:
#   cd /path/to/embodied-claude
#   sudo KOYORI_WEBUI_URL='http://ma-home.local:8080/projects/C:/Users/ma/src/embodied-claude' \
#     ./scripts/koyori-kiosk/install-koyori-kiosk.sh
#
# Reboot, then expect fullscreen webui. Logs: journalctl -u lightdm -b

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8080/projects/C:/Users/ma/src/embodied-claude}"
KIOSK_ENV="/etc/default/koyori-kiosk"

install -m 755 "$SCRIPT_DIR/koyori-kiosk.sh" /usr/local/bin/koyori-kiosk
install -m 644 "$SCRIPT_DIR/koyori-kiosk.desktop" /usr/share/xsessions/koyori-kiosk.desktop

cat >"$KIOSK_ENV" <<EOF
# Koyori Chromium kiosk target (ma-home claude-code-webui)
KOYORI_WEBUI_URL='$WEBUI_URL'
EOF
chmod 644 "$KIOSK_ENV"

install -d -m 755 /etc/lightdm/lightdm.conf.d
install -m 644 "$SCRIPT_DIR/lightdm-autologin.conf" /etc/lightdm/lightdm.conf.d/koyori-kiosk.conf

if id ma &>/dev/null; then
  usermod -aG video,input ma 2>/dev/null || true
fi

systemctl enable --now iptsd 2>/dev/null || true
systemctl enable lightdm
systemctl set-default graphical.target

echo "Installed koyori kiosk."
echo "  webui: $WEBUI_URL"
echo "  config: $KIOSK_ENV"
echo ""
echo "Reboot to start kiosk:"
echo "  sudo reboot"
