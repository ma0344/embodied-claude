#!/usr/bin/env bash
# Switch LM Studio model ID in repo config (ma-server / Linux dev).
# ma-home の本番運用は set-lmstudio-model.ps1 を使う。
#
# Usage:
#   ./scripts/set-lmstudio-model.sh google/gemma-4-12b-qat
#   ./scripts/set-lmstudio-model.sh google/gemma-4-12b-qat --dry-run

set -euo pipefail

MODEL="${1:-}"
DRY_RUN=0
if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

if [[ -z "$MODEL" ]]; then
  echo "Usage: $0 <model-id> [--dry-run]" >&2
  echo "Example: $0 google/gemma-4-12b-qat" >&2
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$REPO/.claude/settings.local.json"
MCP="$REPO/.mcp.json"

export REPO MODEL SETTINGS MCP DRY_RUN
python3 <<'PY'
import json
import os
from pathlib import Path

repo = Path(os.environ["REPO"])
model = os.environ["MODEL"]
dry = os.environ["DRY_RUN"] == "1"
settings = Path(os.environ["SETTINGS"])
mcp = Path(os.environ["MCP"])

model_keys = [
    "ANTHROPIC_MODEL",
    "CLAUDE_MODEL",
    "LMSTUDIO_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "LM_STUDIO_VISION_MODEL",
]

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def dump(path: Path, data):
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry:
        print(f"  would write {path}")
        return
    path.write_text(text, encoding="utf-8")

print("==> set-lmstudio-model")
print(f"    target: {model}")
if dry:
    print("    mode:   dry-run")
print()

if settings.is_file():
    data = load(settings)
    prev = data.get("model", "(unset)")
    data["model"] = model
    env = data.setdefault("env", {})
    print("  settings.local.json")
    if prev != model:
        print(f"    set model: {prev} -> {model}")
    for key in model_keys:
        cur = env.get(key)
        if cur != model:
            print(f"    set env.{key}: {cur} -> {model}")
            env[key] = model
    dump(settings, data)
else:
    print(f"  skip settings.local.json (missing {settings})")

if mcp.is_file():
    data = load(mcp)
    servers = data.get("mcpServers", {})
    wifi = servers.get("wifi-cam", {})
    env = wifi.setdefault("env", {})
    print("")
    print("  .mcp.json (wifi-cam vision)")
    for key in ("CLAUDE_MODEL", "LM_STUDIO_VISION_MODEL"):
        cur = env.get(key)
        if cur != model:
            print(f"    set mcpServers.wifi-cam.env.{key}: {cur} -> {model}")
            env[key] = model
    dump(mcp, data)
else:
    print("")
    print(f"  skip .mcp.json (missing {mcp})")

print("")
if dry:
    print("Re-run without --dry-run to apply.")
else:
    print("Next:")
    print(f"  1. ma-home LM Studio: load {model}, start Local Server")
    print("  2. ma-home: .\\scripts\\check-lmstudio-model.ps1")
    print("  3. Docs: docs/lmstudio-model-change.md")
PY
