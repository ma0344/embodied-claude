# 運用スクリプト早見（ma-home）

**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md) § B  
**診断の入口**: `.\scripts\check-koyori-stack.ps1`、`.\scripts\post-logon-smoke.ps1`

リポジトリルート `scripts/` から実行（PowerShell 除非記載）。

---

## 常駐・起動

| スクリプト | 用途 |
|-----------|------|
| `install-memory-daemon-task.ps1` | Memory HTTP `:18900` Task |
| `restart-memory-mcp.ps1` | :18900 再起動（`uv sync` + health/recall 確認） |
| `install-presence-ui-task.ps1` | presence-ui `:8090` Task |
| `install-aivis-tts-task.ps1` | AivisSpeech TTS Task |
| `install-embodied-watchdog-task.ps1` | 2 分間隔 Watchdog |
| `install-autonomous-tick-task.ps1` | 15m desire-updater + autonomous-tick |
| `install-webui-task.ps1` | claude-code-webui `:8080`（**任意**） |
| `restart-presence-ui.ps1` | :8090 再起動（sociality 変更時は deps sync 込み） |
| `run-memory-daemon.ps1` | :18900 前景起動 |
| `run-webui-ma-home.ps1` | :8080 起動 |
| `run-claude-local.ps1` | CLI（`--model` 付き） |
| `run-autonomous-tick.ps1` | 自律 tick 手動 1 回 |

---

## 診断・スモーク

| スクリプト | 用途 |
|-----------|------|
| `check-koyori-stack.ps1` | スタック診断（LM Studio 手動ロード警告含む） |
| `post-logon-smoke.ps1` | ログオン後スモーク（:8080 optional） |
| `verify-mission-a.ps1` | ミッション A（stack + 任意 chat） |
| `test-memory-stack.ps1` | 記憶スタック自動スモーク |
| `test-gateway-direct-actions.ps1` | A3 gateway 直実行 |
| `check-lmstudio-model.ps1` | モデル ID 不一致チェック |
| `watch-embodied-health.ps1` | ハング検出・daemon 再起動 |

---

## LM Studio・人格

| スクリプト | 用途 |
|-----------|------|
| `set-lmstudio-model.ps1` | チャット / `-VisionModel` 更新 |
| `sync-lmstudio-settings.ps1` | env を top `model` に揃える |
| `open-soul-core-for-lmstudio.ps1` | SOUL.core を LM Studio 用に開く |
| `enable-rp-phase1-ma-home.ps1` | `PRESENCE_SOUL_CORE_IN_APPEND=0` |
| `export-persona-lora-jsonl.py` | RP-2a LoRA 学習用 export |

---

## Open loops・記憶メンテ

| スクリプト | 用途 |
|-----------|------|
| `purge-noise-open-loops.py` | エージェント台詞ノイズ loop を close |
| `purge-stale-open-loops.py` | 過去日付 loop を close |
| `purge-archive-open-loops.py` | 保管系「覚えておいて」loop 掃除 |
| `score-stm-entries.py` | MEM-5 採点手計算 |
| `sociality-mcp/.../purge-archive-open-loops.py` | 上記（relationship パッケージ内） |

OL 運用詳細 → [open-loops-reminders.md](../architecture/open-loops-reminders.md)

---

## Outbound・通知

| スクリプト | 用途 |
|-----------|------|
| `setup-ntfy-ma-home.ps1` | ntfy topic + `presence-ui.local.env` |

**Outbound スモーク**:

```powershell
curl -X POST http://localhost:8090/api/v1/autonomous-tick `
  -H "Content-Type: application/json" `
  -d '{"smoke_action":"miss_companion","speech_text":"まー、おる？"}'
```

Surface `?kiosk=1` で着信 →「返事する」→ 新規会話。

**A4f 登録後**:

```powershell
Start-ScheduledTask -TaskName EmbodiedClaude-AutonomousTick
Get-Content $env:USERPROFILE\.config\embodied-claude\logs\autonomous-tick.log -Tail 5
```

チャネル詳細 → [outbound-channels.md](../architecture/outbound-channels.md)

---

## 開発・PoC

| スクリプト | 用途 |
|-----------|------|
| `c1-native-poc.ps1` | Native PoC ON/OFF（`-Enable` / `-Disable`） |
| `sync-presence-deps.ps1` | presence-ui .venv へ MCP 再ビルド |
| `tts_benchmark.py` | TTS 計測 |
| `wifi-cam-mcp/scripts/test_ptz_probe.py` | Tapo PTZ 切り分け |

---

## 前提

- LM Studio 手動ロード（B2 🪦）
- `.claude/settings.local.json`、`.mcp.json`
- memory は `uv run --no-sync`（stdio と daemon 二重にしない — [lmstudio-kv-cache.md](./lmstudio-kv-cache.md)）
