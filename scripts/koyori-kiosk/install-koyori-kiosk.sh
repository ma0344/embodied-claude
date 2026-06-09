#!/usr/bin/env bash
# Install lightdm autologin + Chromium kiosk session on koyori (Surface Go).
#
# Run on koyori after base packages:
#   sudo apt install -y xorg x11-common lightdm lightdm-gtk-greeter \
#     chromium-browser unclutter iptsd x11-xserver-utils dbus-x11 \
#     ibus-mozc fonts-noto-cjk
#
# Usage:
#   cd /path/to/koyori-kiosk   # or embodied-claude/scripts/koyori-kiosk
#   sudo ./install-koyori-kiosk.sh
#
# Logs after reboot:
#   cat /tmp/koyori-kiosk.log
#   journalctl -u lightdm -b --no-pager | tail -30

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8080/projects/C:/Users/ma/src/embodied-claude}"
KIOSK_ENV="/etc/default/koyori-kiosk"

missing=()
for pkg in x11-common lightdm; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing+=("$pkg")
  fi
done
if ((${#missing[@]})); then
  echo "Installing missing packages: ${missing[*]}" >&2
  apt-get update
  apt-get install -y "${missing[@]}"
fi

if [[ ! -x /etc/X11/Xsession ]]; then
  echo "ERROR: /etc/X11/Xsession missing. Run: sudo apt install -y x11-common" >&2
  exit 1
fi

install -m 755 "$SCRIPT_DIR/koyori-kiosk.sh" /usr/local/bin/koyori-kiosk
install -m 755 "$SCRIPT_DIR/koyori-ime-start.sh" /usr/local/bin/koyori-ime-start
install -m 755 "$SCRIPT_DIR/koyori-diagnose-ime.sh" /usr/local/bin/koyori-diagnose-ime

IME_PKGS=(ibus-mozc ibus-gtk3 ibus-gtk mozc-server fonts-noto-cjk firefox)
missing_ime=()
for pkg in "${IME_PKGS[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing_ime+=("$pkg")
  fi
done
if ((${#missing_ime[@]})); then
  echo "Installing IME + kiosk browser: ${missing_ime[*]}"
  apt-get install -y "${missing_ime[@]}"
fi

install -d -m 755 /usr/share/xsessions
install -m 644 "$SCRIPT_DIR/koyori-kiosk.desktop" /usr/share/xsessions/koyori-kiosk.desktop
install -m 644 "$SCRIPT_DIR/lightdm-xsession.desktop" /usr/share/xsessions/lightdm-xsession.desktop

MA_HOME="/home/ma"
if id ma &>/dev/null && [[ -d "$MA_HOME" ]]; then
  install -o ma -g ma -m 755 "$SCRIPT_DIR/xsession" "$MA_HOME/.xsession"
  usermod -aG video,input ma 2>/dev/null || true
  if command -v im-config >/dev/null 2>&1; then
    runuser -u ma -- im-config -n ibus 2>/dev/null || true
  fi
else
  echo "WARN: user ma or $MA_HOME not found; create ~/.xsession manually" >&2
fi

cat >"$KIOSK_ENV" <<EOF
# Koyori Chromium kiosk target (ma-home claude-code-webui)
#
# Tip: if the kiosk shows "This site can't be reached", ma-home.local may resolve
# to IPv6 while webui listens on IPv4. Use ma-home's LAN IPv4 (or Tailscale IP):
#   KOYORI_WEBUI_URL='http://192.168.x.x:8080/projects/C:/Users/ma/src/embodied-claude'
KOYORI_WEBUI_URL='$WEBUI_URL'
KOYORI_CHROMIUM_NO_SANDBOX=1
# firefox: IBus/Mozc works on minimal X. snap chromium often cannot use host IME.
KOYORI_BROWSER=firefox
EOF
chmod 644 "$KIOSK_ENV"

install -d -m 755 /etc/lightdm/lightdm.conf.d
install -m 644 "$SCRIPT_DIR/lightdm-autologin.conf" /etc/lightdm/lightdm.conf.d/koyori-kiosk.conf

# Optional USB dongle tweaks (off by default; set KOYORI_USB_POWER=1 to enable).
if [[ "${KOYORI_USB_POWER:-0}" == "1" ]] && [[ -f "$SCRIPT_DIR/koyori-usb-power-on.sh" ]]; then
  install -m 755 "$SCRIPT_DIR/koyori-usb-power-on.sh" /usr/local/sbin/koyori-usb-power-on.sh
  install -m 644 "$SCRIPT_DIR/99-koyori-usb-power.rules" /etc/udev/rules.d/99-koyori-usb-power.rules
  install -m 644 "$SCRIPT_DIR/koyori-usb-power.service" /etc/systemd/system/koyori-usb-power.service
  systemctl daemon-reload
  systemctl enable koyori-usb-power.service
  /usr/local/sbin/koyori-usb-power-on.sh || true
  udevadm control --reload-rules 2>/dev/null || true
  if ! grep -q 'usbcore.autosuspend=-1' /etc/default/grub 2>/dev/null; then
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="usbcore.autosuspend=-1 /' /etc/default/grub
    update-grub 2>/dev/null || true
  fi
fi
install -m 755 "$SCRIPT_DIR/diagnose-usb-c.sh" /usr/local/bin/koyori-diagnose-usb-c
install -m 755 "$SCRIPT_DIR/fix-usb-c.sh" /usr/local/bin/koyori-fix-usb-c

systemctl enable --now iptsd 2>/dev/null || true
systemctl enable lightdm
systemctl set-default graphical.target

echo "Installed koyori kiosk."
echo "  sessions: /usr/share/xsessions/koyori-kiosk.desktop"
echo "  webui:    $WEBUI_URL"
echo "  config:   $KIOSK_ENV"
echo "  log:      /tmp/koyori-kiosk.log"
echo ""
echo "Verify:"
echo "  ls /usr/share/xsessions/"
echo "  cat /etc/lightdm/lightdm.conf.d/koyori-kiosk.conf"
echo ""
echo "USB-C / Travel Hub dead after boot:"
echo "  sudo koyori-fix-usb-c"
echo "  docs/koyori-usb-c-recovery.md"
echo ""
echo "Reboot:"
echo "  sudo reboot"
echo ""
echo "Japanese IME in kiosk:"
echo "  Ctrl+Space toggles Mozc"
echo "  diagnose: koyori-diagnose-ime"
echo "  log: grep ime /tmp/koyori-kiosk.log"
