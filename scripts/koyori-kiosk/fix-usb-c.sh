#!/usr/bin/env bash
# Surface Go (koyori) USB-C recovery helper.
#
# Symptom: lsusb -t shows only internal BT; Travel Hub / Ethernet / keyboard invisible.
#
# Usage:
#   sudo ./fix-usb-c.sh              # diagnose + suggest next step
#   sudo ./fix-usb-c.sh reload       # reload UCSI stack (safe, try first)
#   sudo ./fix-usb-c.sh list-kernels    # installed images (GRUB only lists these)
#   sudo ./fix-usb-c.sh list-available  # older kernels in linux-surface apt repo
#   sudo ./fix-usb-c.sh install 6.18.7-surface-1   # install + update-grub
#   sudo ./fix-usb-c.sh reboot-hint
#
# Permanent kernel pin (if older kernel works):
#   sudo apt install linux-image-6.8.*-surface-*   # example; use list-kernels output
#   sudo apt-mark hold linux-image-surface linux-headers-surface

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0 [command]" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CMD=${1:-diagnose}

ucsi_errors() {
  dmesg 2>/dev/null | grep -iE 'ucsi|USBC000|GET_CONNECTOR_STATUS|typec_ucsi' || true
}

usb_tree_ok() {
  lsusb -t 2>/dev/null | grep -qE 'Hub|045e|0bda|Class=Hub' && return 0
  lsusb 2>/dev/null | grep -qE '045e|0bda|Hub' && return 0
  return 1
}

cmd_diagnose() {
  echo "=== koyori USB-C recovery ==="
  echo "kernel: $(uname -r)"
  echo ""

  if [[ -x /usr/local/bin/koyori-diagnose-usb-c ]]; then
    /usr/local/bin/koyori-diagnose-usb-c
  elif [[ -x "$SCRIPT_DIR/diagnose-usb-c.sh" ]]; then
    bash "$SCRIPT_DIR/diagnose-usb-c.sh"
  fi

  echo ""
  echo "=== UCSI errors (if any) ==="
  ucsi_errors | tail -20 || echo "  (none in dmesg)"

  echo ""
  if usb_tree_ok; then
    echo "OK: external USB/hub visible in lsusb."
  else
    echo "FAIL: no Travel Hub / Ethernet / Logitech in lsusb."
    echo ""
    echo "Suggested order:"
    echo "  1) sudo $0 reload"
    echo "  2) Power off fully (not reboot), plug Travel Hub, then power on"
    echo "  3) sudo $0 list-kernels  → boot older linux-surface from GRUB Advanced"
    echo "  4) If older kernel works: apt-mark hold linux-image-surface"
    echo ""
    echo "While plugged: sudo dmesg -w"
  fi
}

cmd_reload() {
  echo "Reloading Type-C / UCSI modules..."
  modprobe -r typec_ucsi 2>/dev/null || true
  sleep 2
  modprobe typec_ucsi 2>/dev/null || modprobe ucsi_acpi 2>/dev/null || true
  sleep 2
  echo ""
  echo "=== lsusb -t ==="
  lsusb -t || lsusb
  echo ""
  ucsi_errors | tail -10 || true
  if usb_tree_ok; then
    echo "Hub/device appeared — test Ethernet: ip -br link"
  else
    echo "Still empty — try cold boot with hub plugged, or older kernel (see list-kernels)."
  fi
}

cmd_list_kernels() {
  echo "=== Installed linux-image packages (GRUB Advanced shows ONLY these) ==="
  dpkg -l 'linux-image-*' 2>/dev/null | awk '/^ii/ {print $2, $3}' | grep -E 'surface|generic|oem' || \
    dpkg -l 'linux-image-*' 2>/dev/null | awk '/^ii/ {print $2, $3}'
  echo ""
  if ! dpkg -l 'linux-image-*' 2>/dev/null | awk '/^ii/ {print $2}' | grep -qE 'surface-[0-9]' || \
     [[ $(dpkg -l 'linux-image-*' 2>/dev/null | awk '/^ii/ && /surface/ {print $2}' | grep -c 'linux-image-[0-9]') -le 1 ]]; then
    echo "Only one surface kernel installed → GRUB has nothing older to pick."
    echo "Install one first:  sudo $0 list-available"
    echo "                  sudo $0 install 6.18.7-surface-1"
  else
    echo "Boot: GRUB → Advanced options → pick an OLDER *-surface-* entry (not the default)."
  fi
  echo "Then (hub plugged): lsusb -t"
  echo ""
  echo "If older works, pin upgrades:"
  echo "  sudo apt-mark hold linux-image-surface linux-headers-surface"
}

cmd_list_available() {
  echo "=== linux-surface apt repo (install explicit version) ==="
  if ! apt-cache show linux-image-surface &>/dev/null; then
    echo "linux-surface apt repo missing. See docs/koyori-usb-c-recovery.md"
    return 1
  fi
  apt-cache search '^linux-image-[0-9].*-surface-' 2>/dev/null | sort -V | tail -25
  echo ""
  echo "Suggested downgrade path from 6.19.8-surface-3:"
  echo "  sudo $0 install 6.18.7-surface-1"
  echo "  (if still broken) sudo $0 install 6.17.13-surface-2"
}

cmd_install() {
  local ver=${1:-}
  if [[ -z "$ver" ]]; then
    echo "Usage: sudo $0 install KERNEL-VERSION" >&2
    echo "Example: sudo $0 install 6.18.7-surface-1" >&2
    exit 1
  fi
  local img="linux-image-${ver}"
  local hdr="linux-headers-${ver}"
  echo "Installing $img and $hdr ..."
  apt-get update
  apt-get install -y "$img" "$hdr"
  update-grub
  echo ""
  echo "Reboot → GRUB → Advanced options for Linux $ver"
  echo "Default entry may still be 6.19 — pick the older line explicitly."
}

cmd_reboot_hint() {
  cat <<'EOF'
Cold-boot procedure (often fixes Surface USB-C after UCSI wedged):

1. Shut down completely:  sudo poweroff   (not reboot)
2. Connect Surface USB-C Travel Hub (and USB power to Surface if needed)
3. Wait 5 seconds, press power
4. After login:  lsusb -t

If still empty at tty (multi-user, no GUI):
  sudo systemctl isolate multi-user.target
  lsusb -t

If USB works on older GRUB kernel but not 6.19.x-surface:
  → kernel regression; hold older surface kernel until linux-surface updates.
EOF
}

case "$CMD" in
  diagnose | "") cmd_diagnose ;;
  reload) cmd_reload ;;
  list-kernels) cmd_list_kernels ;;
  list-available) cmd_list_available ;;
  install) cmd_install "${2:-}" ;;
  reboot-hint) cmd_reboot_hint ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Commands: diagnose | reload | list-kernels | list-available | install VER | reboot-hint" >&2
    exit 1
    ;;
esac
