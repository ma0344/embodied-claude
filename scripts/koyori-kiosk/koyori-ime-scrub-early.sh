#!/bin/sh
# Clear stale IBus engine names before im-config / ibus-daemon reads dconf (Xsession.d).
# Installed as /etc/X11/Xsession.d/65koyori-ime-scrub

if ! command -v gsettings >/dev/null 2>&1; then
  exit 0
fi

gsettings set org.freedesktop.ibus.general preload-engines "[]" 2>/dev/null || true
gsettings set org.freedesktop.ibus.general engines-order "[]" 2>/dev/null || true
