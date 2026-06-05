#!/usr/bin/env bash
# One-shot setup for ma-server (legacy Core2 CPU, LM Studio on ma-home).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.local/node/bin:${PATH:-}"

echo "==> embodied-claude setup (ma-server)"
echo "    repo: $REPO"

if ! command -v uv >/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck source=/dev/null
  source "${HOME}/.local/bin/env"
fi

if ! command -v ffmpeg >/dev/null; then
  echo "WARN: ffmpeg not found. Install: sudo apt install ffmpeg mpv"
fi

cd "$REPO"
./scripts/install-mcps.sh || {
  echo "WARN: install-mcps.sh had errors; fixing numpy on memory/sociality..."
  for d in memory-mcp sociality-mcp; do
    (cd "$d" && echo "3.12" > .python-version && UV_PYTHON=3.12 uv sync)
  done
}

if [ ! -f "$REPO/.mcp.json" ]; then
  echo "WARN: .mcp.json missing — copy from .mcp.json.example or use repo template"
fi

if ! command -v claude >/dev/null; then
  if [ ! -x "${HOME}/.local/node/bin/npm" ]; then
    echo "Installing Node.js locally..."
    mkdir -p "${HOME}/.local/node"
    curl -fsSL https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-x64.tar.xz \
      | tar -xJ -C "${HOME}/.local/node" --strip-components=1
  fi
  npm install -g @anthropic-ai/claude-code
fi

mkdir -p "${HOME}/.config/embodied-claude"
echo ""
echo "Next steps:"
echo "  1. Edit $REPO/.mcp.json (camera TAPO_* credentials)"
echo "  2. Put LM Studio token: ${HOME}/.config/embodied-claude/lmstudio.token"
echo "  3. source $REPO/scripts/env-lmstudio.sh && claude --model <lm-studio-model-id>"
echo "  4. Add to ~/.bashrc: export PATH=\"\$HOME/.local/bin:\$HOME/.local/node/bin:\$PATH\""
