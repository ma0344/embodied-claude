#!/usr/bin/env bash
# LM Studio (ma-home) を Claude Code の API 先にするための環境変数。
#
# 重要: ma-server は Core2 世代 CPU のため Claude Code CLI は動きません
# (Illegal instruction)。Claude Code は ma-home で起動し、MCP は SSH 先の
# このリポジトリを ma-home から見えるようにするか、ma-home にも clone してください。
#
# ma-home で:
#   source /path/to/embodied-claude/scripts/env-lmstudio.sh
#   export ANTHROPIC_BASE_URL=http://127.0.0.1:1234
#   claude --model "<model-id-from-lm-studio>"
#
# モデル ID の変更手順: docs/lmstudio-model-change.md
#   ma-home: .\scripts\set-lmstudio-model.ps1 -Model <id>
#
# ma-server では Cursor + .mcp.json の MCP を使う構成が現実的です。
#
# Set LM_STUDIO_TOKEN in ~/.config/embodied-claude/lmstudio.token (chmod 600)
# or export it in your shell profile.

set -euo pipefail

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://ma-home.local:1234}"

_token_file="${HOME}/.config/embodied-claude/lmstudio.token"
if [ -z "${LM_STUDIO_TOKEN:-}" ] && [ -f "$_token_file" ]; then
  LM_STUDIO_TOKEN="$(tr -d '[:space:]' < "$_token_file")"
fi

if [ -n "${LM_STUDIO_TOKEN:-}" ]; then
  export ANTHROPIC_AUTH_TOKEN="$LM_STUDIO_TOKEN"
else
  echo "WARN: LM_STUDIO_TOKEN unset. Create $_token_file or export LM_STUDIO_TOKEN." >&2
  export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-lmstudio}"
fi

export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"
export CLAUDE_CODE_DISABLE_THINKING="${CLAUDE_CODE_DISABLE_THINKING:-1}"

# Claude Code が読む場合がある（LM Studio は Bearer = AUTH_TOKEN と同じ値でよい）
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${ANTHROPIC_AUTH_TOKEN}}"

# ma-server から確認済みのモデル ID（LM Studio にロード済みのものと一致させる）
export CLAUDE_MODEL="${CLAUDE_MODEL:-google/gemma-4-12b-qat}"
export LMSTUDIO_MODEL="${LMSTUDIO_MODEL:-$CLAUDE_MODEL}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${ANTHROPIC_DEFAULT_SONNET_MODEL:-$CLAUDE_MODEL}"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${ANTHROPIC_DEFAULT_OPUS_MODEL:-$CLAUDE_MODEL}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-$CLAUDE_MODEL}"
export CLAUDE_CODE_SUBAGENT_MODEL="${CLAUDE_CODE_SUBAGENT_MODEL:-$CLAUDE_MODEL}"

echo "ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
echo "ANTHROPIC_AUTH_TOKEN is set: $([ -n \"${ANTHROPIC_AUTH_TOKEN}\" ] && echo yes || echo no)"
