#!/usr/bin/env bash
# Run ON ma-home from the embodied-claude repo root.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.local/node/bin:${PATH:-}"

# LM Studio on this machine
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:1234}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"

# shellcheck source=/dev/null
source "$REPO/scripts/env-lmstudio.sh"

# LM Studio accepts Bearer token; Claude Code may read either variable.
export ANTHROPIC_API_KEY="${ANTHROPIC_AUTH_TOKEN}"

MODEL="${CLAUDE_MODEL:-google/gemma-4-12b}"

echo "Starting Claude Code in $REPO"
echo "  model: $MODEL"
echo "  API:   $ANTHROPIC_BASE_URL"

cd "$REPO"
exec claude --model "$MODEL" "$@"
