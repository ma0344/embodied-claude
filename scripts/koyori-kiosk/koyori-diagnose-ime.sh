#!/usr/bin/env bash
# Diagnose Japanese IME on koyori (run over SSH while kiosk session is active).
#
#   ./koyori-diagnose-ime.sh
#   DISPLAY=:0 ./koyori-diagnose-ime.sh

set -euo pipefail

UID_NUM=$(id -u)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi
export DISPLAY="${DISPLAY:-:0}"

echo "==> koyori IME diagnose"
echo "    user=$USER uid=$UID_NUM DISPLAY=$DISPLAY"
echo ""

for pkg in ibus-mozc ibus-gtk3 ibus-gtk mozc-server fonts-noto-cjk firefox; do
  if dpkg -s "$pkg" >/dev/null 2>&1; then
    echo "  pkg $pkg: installed"
  else
    echo "  pkg $pkg: MISSING"
  fi
done

echo ""
if [[ -x /usr/local/bin/koyori-ime-start ]]; then
  echo "  koyori-ime-start: yes"
else
  echo "  koyori-ime-start: MISSING (re-run sudo ./install-koyori-kiosk.sh)"
fi

if pgrep -u "$UID_NUM" -x ibus-daemon >/dev/null; then
  echo "  ibus-daemon: running ($(pgrep -u "$UID_NUM" -x ibus-daemon))"
else
  echo "  ibus-daemon: not running"
fi

echo ""
echo "  ibus list-engine:"
if command -v ibus >/dev/null 2>&1; then
  ibus list-engine 2>&1 | sed 's/^/    /' || true
  echo ""
  echo "  ibus engine (current): $(DISPLAY=$DISPLAY ibus engine 2>/dev/null || echo '?')"
else
  echo "    (ibus CLI missing)"
fi

echo ""
echo "  recent kiosk log:"
if [[ -f /tmp/koyori-kiosk.log ]]; then
  grep -E 'ime:|koyori-kiosk start|browser=' /tmp/koyori-kiosk.log | tail -15 | sed 's/^/    /' || echo "    (no ime/browser lines — old kiosk script?)"
else
  echo "    /tmp/koyori-kiosk.log missing"
fi

CH=$(command -v chromium-browser 2>/dev/null || command -v chromium 2>/dev/null || true)
if [[ -n "$CH" ]]; then
  echo ""
  if readlink -f "$CH" 2>/dev/null | grep -q snap; then
    echo "  WARN: chromium is snap — Japanese IME often fails; use KOYORI_BROWSER=firefox"
  else
    echo "  chromium path: $CH"
  fi
fi

echo ""
echo "Toggle in Firefox: 半/全 (JIS) or Ctrl+Space. Romaji: konnichiwa → こんにちは"
echo "Input Leap: Mozc → Ctrl+Shift+Space toggle (see docs/koyori-kiosk-ime.md)"
echo "  half/full key arrives as backtick via Leap (US routing)"
echo "If mozc-jp is listed above, IME is ready even when ibus engine shows xkb:*."
echo ""
echo "Fix:"
echo "  cd .../scripts/koyori-kiosk && sudo ./install-koyori-kiosk.sh && sudo reboot"
echo "  /etc/default/koyori-kiosk: KOYORI_BROWSER=firefox"
