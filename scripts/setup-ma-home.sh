#!/usr/bin/env bash
# Run this script ON ma-home Linux (not ma-server, not Windows).
# Windows (PowerShell): use scripts/setup-ma-home.ps1 instead.
set -euo pipefail

REPO="${1:-$HOME/src/embodied-claude}"
export PATH="${HOME}/.local/bin:${HOME}/.local/node/bin:${PATH:-}"

echo "==> embodied-claude setup (ma-home)"
echo "    repo: $REPO"

if [ ! -d "$REPO/.git" ] && [ ! -f "$REPO/pyproject.toml" ] && [ ! -f "$REPO/memory-mcp/pyproject.toml" ]; then
  echo "Clone the repo first, e.g.:"
  echo "  git clone https://github.com/kmizu/embodied-claude.git $REPO"
  exit 1
fi

if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck source=/dev/null
  source "${HOME}/.local/bin/env"
fi

if ! command -v ffmpeg >/dev/null; then
  echo "WARN: install ffmpeg: sudo apt install ffmpeg mpv"
fi

cd "$REPO"
./scripts/install-mcps.sh

if [ ! -f "${HOME}/.config/embodied-claude/lmstudio.token" ]; then
  echo "Create LM Studio token file:"
  echo "  mkdir -p ~/.config/embodied-claude"
  echo "  echo 'YOUR_LM_STUDIO_TOKEN' > ~/.config/embodied-claude/lmstudio.token"
  echo "  chmod 600 ~/.config/embodied-claude/lmstudio.token"
fi

if ! command -v claude >/dev/null; then
  if [ ! -x "${HOME}/.local/node/bin/npm" ]; then
    mkdir -p "${HOME}/.local/node"
    curl -fsSL https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-x64.tar.xz \
      | tar -xJ -C "${HOME}/.local/node" --strip-components=1
  fi
  npm install -g @anthropic-ai/claude-code
fi

if [ ! -f "$REPO/.mcp.json" ]; then
  cp "$REPO/.mcp.json.example" "$REPO/.mcp.json" 2>/dev/null || true
  echo "Edit $REPO/.mcp.json (absolute paths + camera credentials)."
fi

echo ""
echo "Test LM Studio:"
echo "  source $REPO/scripts/env-lmstudio.sh"
echo "  export ANTHROPIC_BASE_URL=http://127.0.0.1:1234"
echo "  cd $REPO && claude --model google/gemma-4-12b"
echo ""
echo "Or: $REPO/scripts/run-claude-local.sh"
