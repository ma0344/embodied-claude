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
#

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8090/}"
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
install -m 755 "$SCRIPT_DIR/koyori-display-setup.sh" /usr/local/bin/koyori-display-setup
install -m 755 "$SCRIPT_DIR/koyori-screen-idle-server.py" /usr/local/bin/koyori-screen-idle-server
install -m 755 "$SCRIPT_DIR/koyori-audio-server.py" /usr/local/bin/koyori-audio-server
install -m 755 "$SCRIPT_DIR/koyori-input-leap-start.sh" /usr/local/bin/koyori-input-leap-start
install -m 755 "$SCRIPT_DIR/koyori-keyboard-layout.sh" /usr/local/bin/koyori-keyboard-layout
install -d -m 755 /usr/local/share/koyori-kiosk
install -m 644 "$SCRIPT_DIR/mozc-kiosk-config.textproto" /usr/local/share/koyori-kiosk/mozc-kiosk-config.textproto
install -m 644 "$SCRIPT_DIR/mozc-ibus-kiosk.textproto" /usr/local/share/koyori-kiosk/mozc-ibus-kiosk.textproto
install -m 755 "$SCRIPT_DIR/koyori-onboard-start.sh" /usr/local/bin/koyori-onboard-start
install -m 755 "$SCRIPT_DIR/koyori-onboard-preseed.sh" /usr/local/bin/koyori-onboard-preseed
install -m 755 "$SCRIPT_DIR/koyori-diagnose-ime.sh" /usr/local/bin/koyori-diagnose-ime
install -m 755 "$SCRIPT_DIR/koyori-diagnose-browser.sh" /usr/local/bin/koyori-diagnose-browser
install -m 755 "$SCRIPT_DIR/koyori-fix-browser-window.sh" /usr/local/bin/koyori-fix-browser-window
install -m 755 "$SCRIPT_DIR/koyori-restart-browser.sh" /usr/local/bin/koyori-restart-browser
install -m 755 "$SCRIPT_DIR/koyori-ime-scrub-early.sh" /etc/X11/Xsession.d/65koyori-ime-scrub
install -m 755 "$SCRIPT_DIR/koyori-ime-preseed.sh" /usr/local/bin/koyori-ime-preseed
install -m 755 "$SCRIPT_DIR/koyori-diagnose-input-leap.sh" /usr/local/bin/koyori-diagnose-input-leap
install -m 755 "$SCRIPT_DIR/koyori-pair-keychron.sh" /usr/local/bin/koyori-pair-keychron
install -m 755 "$SCRIPT_DIR/koyori-connect-keychron.sh" /usr/local/bin/koyori-connect-keychron
install -m 755 "$SCRIPT_DIR/koyori-bluetooth-cleanup-keychron.sh" /usr/local/bin/koyori-bluetooth-cleanup-keychron
install -m 644 "$SCRIPT_DIR/koyori-bluetooth-keychron-lib.sh" /usr/local/bin/koyori-bluetooth-keychron-lib.sh
install -m 755 "$SCRIPT_DIR/koyori-bluetooth-keychron-watch.sh" /usr/local/bin/koyori-bluetooth-keychron-watch
install -d -m 755 /etc/bluetooth/main.conf.d
install -m 644 "$SCRIPT_DIR/99-koyori-bluetooth-keychron.conf" /etc/bluetooth/main.conf.d/99-koyori-keychron.conf

KIOSK_PKGS=(openbox xdotool x11-xserver-utils bluez wmctrl)
missing_kiosk=()
for pkg in "${KIOSK_PKGS[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing_kiosk+=("$pkg")
  fi
done
if ((${#missing_kiosk[@]})); then
  echo "Installing kiosk display packages: ${missing_kiosk[*]}"
  apt-get install -y "${missing_kiosk[@]}"
fi

MA_HOME="/home/ma"
if [[ "${KOYORI_TOUCH_KB:-0}" == "1" ]]; then
  apt-get install -y onboard at-spi2-core 2>/dev/null || true
  /usr/local/bin/koyori-onboard-preseed "$MA_HOME"
fi

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

if id ma &>/dev/null && [[ -d "$MA_HOME" ]]; then
  if [[ -d "$MA_HOME/snap/firefox/common" ]]; then
    FF_PROFILE="$MA_HOME/snap/firefox/common/.mozilla/koyori-kiosk"
  else
    FF_PROFILE="$MA_HOME/.mozilla/koyori-kiosk"
  fi
  install -d -o ma -g ma -m 700 "$FF_PROFILE"
  install -o ma -g ma -m 644 "$SCRIPT_DIR/firefox-kiosk-user.js" "$FF_PROFILE/user.js"
  # Snap Firefox cannot read /var/lib; remove legacy path if present.
  rm -rf /var/lib/koyori/firefox-kiosk 2>/dev/null || true
  echo "  firefox profile: $FF_PROFILE"
  OB_DIR="$MA_HOME/.config/openbox"
  install -d -o ma -g ma -m 755 "$OB_DIR"
  install -o ma -g ma -m 644 "$SCRIPT_DIR/openbox-kiosk-rc.xml" "$OB_DIR/rc.xml"
  echo "  openbox rc: $OB_DIR/rc.xml"
fi

install -d -m 755 /usr/share/xsessions
install -m 644 "$SCRIPT_DIR/koyori-kiosk.desktop" /usr/share/xsessions/koyori-kiosk.desktop
install -m 644 "$SCRIPT_DIR/lightdm-xsession.desktop" /usr/share/xsessions/lightdm-xsession.desktop

if id ma &>/dev/null && [[ -d "$MA_HOME" ]]; then
  install -o ma -g ma -m 755 "$SCRIPT_DIR/xsession" "$MA_HOME/.xsession"
  usermod -aG video,input ma 2>/dev/null || true
  if command -v im-config >/dev/null 2>&1; then
    runuser -u ma -- im-config -n ibus 2>/dev/null || true
  fi
  /usr/local/bin/koyori-ime-preseed ma
else
  echo "WARN: user ma or $MA_HOME not found; create ~/.xsession manually" >&2
fi

SAVE_INPUT_LEAP_SERVER=""
SAVE_INPUT_LEAP_NAME=""
SAVE_INPUT_LEAP_CRYPTO=""
SAVE_WEBUI_URL=""
if [[ -f "$KIOSK_ENV" ]]; then
  # shellcheck disable=SC1091
  source "$KIOSK_ENV" 2>/dev/null || true
  SAVE_INPUT_LEAP_SERVER="${KOYORI_INPUT_LEAP_SERVER:-}"
  SAVE_INPUT_LEAP_NAME="${KOYORI_INPUT_LEAP_NAME:-}"
  SAVE_INPUT_LEAP_CRYPTO="${KOYORI_INPUT_LEAP_CRYPTO:-}"
  SAVE_WEBUI_URL="${KOYORI_WEBUI_URL:-}"
fi
if [[ -n "$SAVE_WEBUI_URL" ]]; then
  WEBUI_URL="$SAVE_WEBUI_URL"
fi

cat >"$KIOSK_ENV" <<EOF
# Koyori kiosk target (ma-home presence-ui / こよりの部屋 :8090)
#
# Tip: if the kiosk shows "This site can't be reached", ma-home.local may resolve to IPv6
# while presence-ui listens on IPv4. Use ma-home's LAN IPv4 (or Tailscale IP):
#   KOYORI_WEBUI_URL='http://192.168.x.x:8090/'
# Do NOT use /projects/... here — that is claude-code-webui (:8080) only.
# Do NOT append kiosk=0 — koyori-kiosk.sh forces ?kiosk=1 for touch layout (C11b).
KOYORI_WEBUI_URL='$WEBUI_URL'
KOYORI_CHROMIUM_NO_SANDBOX=1
# firefox: IBus/Mozc works on minimal X. snap chromium often cannot use host IME.
KOYORI_BROWSER=firefox
# Surface Go native mode (optional; xrandr --auto usually enough):
# KOYORI_DISPLAY_MODE=1800x1200
# KOYORI_USE_WM=1
# Touch keyboard: deferred (docs/backlog-koyori.md). Enable: KOYORI_ONBOARD=1
KOYORI_ONBOARD=0
# C11g screen blank: DPMS standby after wakeLock release (seconds)
KOYORI_DPMS_OFF_SEC=60
# Optional kernel console blank (reboot): KOYORI_CONSOLEBLANK_SEC=900 sudo ./install-koyori-kiosk.sh
EOF

if [[ -n "$SAVE_INPUT_LEAP_SERVER" ]]; then
  cat >>"$KIOSK_ENV" <<EOF
# Input Leap client — preserved from previous install
KOYORI_INPUT_LEAP_SERVER='$SAVE_INPUT_LEAP_SERVER'
KOYORI_INPUT_LEAP_NAME='${SAVE_INPUT_LEAP_NAME:-koyori}'
KOYORI_INPUT_LEAP_CRYPTO=${SAVE_INPUT_LEAP_CRYPTO:-0}
KOYORI_INPUT_LEAP_WATCH=1
KOYORI_INPUT_LEAP_SERVER_WAIT_SEC=120
EOF
else
  cat >>"$KIOSK_ENV" <<'EOF'
# Input Leap client — ma-home Windows Server (uncomment to enable):
# KOYORI_INPUT_LEAP_SERVER='192.168.10.100'
# KOYORI_INPUT_LEAP_NAME='koyori'
# KOYORI_INPUT_LEAP_CRYPTO=0
# KOYORI_INPUT_LEAP_WATCH=1
# KOYORI_INPUT_LEAP_SERVER_WAIT_SEC=120
EOF
fi

cat >>"$KIOSK_ENV" <<EOF
# ma-home が日本語配列なら jp（Input Leap 有効時は未設定でも jp になる）
KOYORI_XKB_LAYOUT=jp
# Keychron BT auto-reconnect in kiosk (background watch)
KOYORI_BT_AUTOCONNECT=1
KOYORI_BT_RECONNECT_INTERVAL=30
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

# Optional kernel consoleblank (Ubuntu Server framebuffer fallback).
if [[ -n "${KOYORI_CONSOLEBLANK_SEC:-}" ]] && [[ -f /etc/default/grub ]]; then
  blank="${KOYORI_CONSOLEBLANK_SEC}"
  if grep -qE 'consoleblank=' /etc/default/grub 2>/dev/null; then
    sed -i -E "s/consoleblank=[0-9]+/consoleblank=${blank}/" /etc/default/grub
  elif grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
    sed -i -E "s/^GRUB_CMDLINE_LINUX_DEFAULT=\"/GRUB_CMDLINE_LINUX_DEFAULT=\"consoleblank=${blank} /" /etc/default/grub
  fi
  update-grub 2>/dev/null || true
  echo "  GRUB consoleblank=${blank} (reboot required)"
fi

systemctl enable --now iptsd 2>/dev/null || true

# Surface hardware volume keys (acpid → PipeWire + kiosk overlay :18791)
ACPI_PKGS=(acpid curl)
missing_acpi=()
for pkg in "${ACPI_PKGS[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing_acpi+=("$pkg")
  fi
done
if ((${#missing_acpi[@]})); then
  echo "Installing volume key packages: ${missing_acpi[*]}"
  apt-get install -y "${missing_acpi[@]}"
fi
install -d -m 755 /etc/acpi/events
install -m 755 "$SCRIPT_DIR/surface-volume.sh" /etc/acpi/surface-volume.sh
install -m 644 "$SCRIPT_DIR/surface-vol-up" /etc/acpi/events/surface-vol-up
install -m 644 "$SCRIPT_DIR/surface-vol-down" /etc/acpi/events/surface-vol-down
systemctl enable --now acpid 2>/dev/null || true

systemctl enable lightdm
systemctl set-default graphical.target

echo "Installed koyori kiosk."
echo "  sessions: /usr/share/xsessions/koyori-kiosk.desktop"
echo "  url:      $WEBUI_URL  (presence-ui :8090)"
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
echo "  Toggle: 半/全 key (JIS) in text fields"
echo "  diagnose: koyori-diagnose-ime"
echo ""
echo "Input:"
echo "  Keychron K4 MAX BT: koyori-pair-keychron.sh / koyori-connect-keychron.sh"
echo "  IME: 半/全 in webui text fields"
echo ""
echo "Screen blank (C11g):"
echo "  kiosk enables DPMS + local http://127.0.0.1:18790/screen-off"
echo "  verify (while kiosk UI is on screen):"
echo "    curl -sS http://127.0.0.1:18790/health; echo"
echo "    ss -ltn | grep 18790"
echo "    grep screen-idle /tmp/koyori-kiosk.log | tail -3"
echo "  SSH alone returns empty if kiosk session is not running or install was skipped."
echo "  optional kernel fallback: KOYORI_CONSOLEBLANK_SEC=900 sudo $0  (then reboot)"
echo "  check: cat /sys/module/kernel/parameters/consoleblank"
echo ""
echo "Hardware volume keys (C11f+):"
echo "  acpid → /etc/acpi/surface-volume.sh → wpctl + http://127.0.0.1:18791/volume-notify"
echo "  verify: curl -sS http://127.0.0.1:18791/health; sudo acpi_listen  # press Vol+/-"
