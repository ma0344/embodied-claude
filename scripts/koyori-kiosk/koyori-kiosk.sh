#!/usr/bin/env bash
# Minimal X session: Chromium fullscreen → ma-home claude-code-webui.
# Installed to /usr/local/bin/koyori-kiosk by install-koyori-kiosk.sh

set -euo pipefail

if [[ -f /etc/default/koyori-kiosk ]]; then
  # shellcheck disable=SC1091
  source /etc/default/koyori-kiosk
fi

WEBUI_URL="${KOYORI_WEBUI_URL:-http://ma-home.local:8080/projects/C:/Users/ma/src/embodied-claude}"

if command -v xset >/dev/null 2>&1; then
  xset s off
  xset -dpms
  xset s noblank
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0 -root &
fi

CHROMIUM=""
for candidate in chromium-browser chromium google-chrome; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CHROMIUM="$candidate"
    break
  fi
done

if [[ -z "$CHROMIUM" ]]; then
  echo "koyori-kiosk: no chromium binary found" >&2
  exit 1
fi

exec "$CHROMIUM" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-translate \
  --autoplay-policy=no-user-gesture-required \
  "$WEBUI_URL"
