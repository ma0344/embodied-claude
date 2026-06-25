#!/bin/sh
# Drop only stale IBus engine names before im-config reads dconf (Xsession.d).
# Installed as /etc/X11/Xsession.d/65koyori-ime-scrub
#
# Do NOT blanket-clear preload to [] — that regressed snap Firefox window mapping.

if ! command -v gsettings >/dev/null 2>&1; then
  exit 0
fi

preload=$(gsettings get org.freedesktop.ibus.general preload-engines 2>/dev/null || true)
order=$(gsettings get org.freedesktop.ibus.general engines-order 2>/dev/null || true)

case "${preload} ${order}" in
  *mozc-on*|*mozc-jp-ro*)
    gsettings set org.freedesktop.ibus.general preload-engines "[]" 2>/dev/null || true
    gsettings set org.freedesktop.ibus.general engines-order "[]" 2>/dev/null || true
    ;;
esac
