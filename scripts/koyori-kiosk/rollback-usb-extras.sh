#!/usr/bin/env bash
# Remove optional USB power / GRUB tweaks from install-koyori-kiosk.sh (koyori).
# Does NOT remove lightdm kiosk session.
#
# Usage: sudo ./rollback-usb-extras.sh

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

systemctl disable koyori-usb-power.service 2>/dev/null || true
rm -f /etc/systemd/system/koyori-usb-power.service
rm -f /etc/udev/rules.d/99-koyori-usb-power.rules
rm -f /usr/local/sbin/koyori-usb-power-on.sh
systemctl daemon-reload
udevadm control --reload-rules 2>/dev/null || true

if [[ -f /etc/default/grub ]] && grep -q 'usbcore.autosuspend=-1' /etc/default/grub; then
  sed -i 's/usbcore.autosuspend=-1 //g' /etc/default/grub
  update-grub 2>/dev/null || true
fi

echo "Removed koyori USB extras. Reboot and test: lsusb -t (with Travel Hub plugged)"
