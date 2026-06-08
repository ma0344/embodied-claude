#!/usr/bin/env bash
# Surface Go USB-C diagnostics (run on koyori).
# Usage: ./diagnose-usb-c.sh

set -euo pipefail

echo "=== USB tree ==="
lsusb -t 2>/dev/null || lsusb

echo ""
echo "=== Networks (hub Ethernet would be enx*/eth*) ==="
ip -br link

echo ""
echo "=== Type-C sysfs ==="
if compgen -G /sys/class/typec/* >/dev/null 2>&1; then
  for p in /sys/class/typec/*; do
    echo "--- $(basename "$p") ---"
    for f in data_role power_role port_type; do
      [[ -f "$p/$f" ]] && echo "  $f: $(cat "$p/$f")"
    done
  done
else
  echo "  (no /sys/class/typec/* — Type-C stack may not be up)"
fi

echo ""
echo "=== UCSI / Type-C kernel modules ==="
lsmod | grep -iE 'ucsi|typec|tcpm' || echo "  (none loaded)"

echo ""
echo "=== Recent USB / Type-C dmesg ==="
dmesg 2>/dev/null | grep -iE 'usb|typec|ucsi|tcpm|hub|045e|0bda' | tail -40 || true

echo ""
echo "=== Boot target / kiosk-related units ==="
systemctl get-default 2>/dev/null || true
systemctl is-enabled lightdm 2>/dev/null || true
systemctl is-enabled koyori-usb-power.service 2>/dev/null || true

echo ""
echo "=== GRUB cmdline ==="
grep GRUB_CMDLINE_LINUX /etc/default/grub 2>/dev/null || true

echo ""
echo "Tip: plug Travel Hub, run again, or: sudo dmesg -w  (while re-plugging)"
