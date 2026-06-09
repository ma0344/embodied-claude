#!/usr/bin/env bash
# Pre-enable onboard for kiosk (no first-run accessibility dialog). Run as root from install.

set -euo pipefail

MA_HOME="${1:-/home/ma}"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if ! id ma &>/dev/null || [[ ! -d "$MA_HOME" ]]; then
  echo "WARN: user ma not found; skip onboard preseed" >&2
  exit 0
fi

ONBOARD_CONF="$MA_HOME/.config/onboard"
install -d -o ma -g ma -m 755 "$ONBOARD_CONF"
if [[ -f "$SCRIPT_DIR/onboard-kiosk.conf" ]]; then
  install -o ma -g ma -m 644 "$SCRIPT_DIR/onboard-kiosk.conf" "$ONBOARD_CONF/onboard.conf"
fi

AUTOSTART="$MA_HOME/.config/autostart"
install -d -o ma -g ma -m 755 "$AUTOSTART"
cat >"$AUTOSTART/onboard.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Hidden=true
EOF
chown ma:ma "$AUTOSTART/onboard.desktop"

preseed() {
  # Avoid "Enable accessibility for auto-show?" dialog — keyboard stays visible instead.
  gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true
  gsettings set org.onboard.auto-show enabled false 2>/dev/null || true
  gsettings set org.onboard.auto-show tablet-mode false 2>/dev/null || true
  gsettings set org.onboard.window.force-to-top true 2>/dev/null || true
  gsettings set org.onboard.icon-palette in-use true 2>/dev/null || true
  gsettings set org.onboard.icon-palette hide-on-touch false 2>/dev/null || true
  gsettings set org.onboard.window.landscape dock-expand true 2>/dev/null || true
  gsettings set org.onboard.window.landscape dock-height 220 2>/dev/null || true
  gsettings set org.onboard.keyboard key-synth 'XTest' 2>/dev/null || true
  gsettings set org.onboard layout 'Compact' 2>/dev/null || true
}

if command -v gsettings >/dev/null 2>&1; then
  runuser -u ma -- bash -c "$(declare -f preseed); preseed" || preseed || true
fi

# System autostart would launch onboard before kiosk and show the dialog again.
for f in /etc/xdg/autostart/onboard.desktop /etc/xdg/autostart/onboard-autostart.desktop; do
  if [[ -f "$f" ]] && ! grep -q '^Hidden=true' "$f" 2>/dev/null; then
    echo "Hidden=true" >>"$f"
  fi
done

echo "  onboard preseed: $ONBOARD_CONF/onboard.conf"
