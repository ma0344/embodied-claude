#!/usr/bin/env bash
# Keep USB ports powered (Logitech dongle on Surface Go USB-C).
# sysctl usbcore.autosuspend is absent on some kernels; use sysfs + per-device power.

set -euo pipefail

autosuspend=/sys/module/usbcore/parameters/autosuspend
if [[ -w "$autosuspend" ]]; then
  echo -1 >"$autosuspend"
fi

shopt -s nullglob
for ctrl in /sys/bus/usb/devices/*/power/control; do
  [[ -w "$ctrl" ]] && echo on >"$ctrl" 2>/dev/null || true
done
for as in /sys/bus/usb/devices/*/power/autosuspend; do
  [[ -w "$as" ]] && echo -1 >"$as" 2>/dev/null || true
done
