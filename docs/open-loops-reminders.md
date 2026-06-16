# Open Loops / リマインド（OL1 + OL2）

**実装**: 2026-06-16  
**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md)、[backlog-ma-home.md](./backlog-ma-home.md)

---

## 何が動くか

### OL1 — 日付解決

- ingest 時に open loop の `detail_json.resolved_date`（`明日` / `今日` / `明後日` → JST カレンダー日）
- 期限切れ loop は ingest / 自律 tick 前の `close_stale_open_loops` で `status=closed`
- 手動掃除: `scripts/purge-stale-open-loops.py`（共有ロジックは `relationship_mcp.date_resolution`）

### OL2 — リマインド

1. 部屋で「10時に〇〇をリマインドして」等 → `create_commitment(due_at)`（`reminder_intent.py`）
2. compose が `list_due_commitments` で `[commitments_due]` を注入（旧 `person_model.commitments` バグ修正済み）
3. 15m 自律 tick: `commitments_due` あり → plan が `remind_commitment` → `remind_commitment_direct`（outbound SSE + PC TTS）→ `complete_commitment`

```powershell
# 手動 tick
.\scripts\run-autonomous-tick.ps1

# ログ
Get-Content $env:USERPROFILE\.config\embodied-claude\logs\autonomous-tick.log -Tail 20
```

---

## デプロイ（presence-ui 更新時）

`relationship-mcp` をコード変更したら **presence-ui の venv に載せ直す**こと。  
`uv sync --reinstall-package` は venv 稼働中（presence-ui / pytest）だと Windows で `pytest.exe` ロックエラーになりやすい。

**推奨（稼働中でも可）**:

```powershell
cd presence-ui
uv pip install --reinstall "relationship-mcp @ file:///C:/Users/ma/src/embodied-claude/sociality-mcp/packages/relationship-mcp"
.\scripts\restart-presence-ui.ps1
```

**venv がアイドルなとき**:

```powershell
cd presence-ui
uv sync --reinstall-package relationship-mcp
```

`sync-presence-deps.ps1` / `restart-presence-ui.ps1` 実行後、compose が `list_due_commitments` を呼べることを確認:

```powershell
uv run python -c "from relationship_mcp.store import RelationshipStore; print(hasattr(RelationshipStore,'list_due_commitments'))"
```

---

## 残リスク・既知の制限（運用メモ）

| 項目 | 内容 | 対策 |
|------|------|------|
| **relationship-mcp の reinstall 忘れ** | 古い venv だと `list_due_commitments` が無く、`commitments_due` が常に空 → リマインドが鳴らない | 上記デプロイ手順。コード変更のたびに `uv pip install --reinstall` + restart |
| **リマインド文面** | 登録時に `「…」` から `speak_line` を抽出し `metadata_json` に保存。鳴るときは `speak_line` をそのまま使用（LLM 生成は Phase B） | `delivery: say \| nudge_only` で音声 on/off |
| **`N分後`** | `10分後に…教えて` / `say でしゃべって` をパース（全角数字対応） | 曖昧な相対表現は未対応 |
| **時刻精度** | Windows タスクは **15分間隔**（18:26 → 次 18:41）。`3分後` は最大 ~15分遅れ | presence-ui **reminder watchdog**（既定60秒、`PRESENCE_REMINDER_POLL_SEC`） |
| **音声（Surface）** | `room_inbound` のみだと SSE 切断時に無音。MCP `say` 経路と別 | `room_say` SSE + **poll フォールバック**（`/api/v1/tts/room-say/pending`） |
| **当日の相対日** | `明日` loop は **会議当日は open のまま**（`include_today=false`）。当日終了後に auto-close | 当日中に閉じたいときは `purge-stale-open-loops.py --include-today` |

---

## コード参照

| モジュール | 役割 |
|-----------|------|
| `relationship_mcp/date_resolution.py` | 相対日付 → `date` |
| `relationship_mcp/reminder_intent.py` | 発話 → `ReminderSpec`（title / due_at / speak_line / delivery） |
| `relationship_mcp/store.py` | ingest / `list_due_commitments` / `close_stale_open_loops` |
| `interaction_orchestrator_mcp/compose.py` | `[commitments_due]` |
| `interaction_orchestrator_mcp/plan.py` | 自律時 commitment 優先 |
| `presence_ui/gateway/direct_actions.py` | `remind_commitment_direct` |
| `presence_ui/gateway/autonomous_tick.py` | tick 前 stale 掃除 |

---

## テスト

```powershell
cd sociality-mcp/packages/relationship-mcp
uv run pytest tests/test_open_loops_reminders.py -v

cd ../interaction-orchestrator-mcp
uv sync --extra dev --reinstall-package relationship-mcp
uv run pytest tests/test_orchestrator.py::TestPlan::test_due_commitments_prioritize_autonomous_reminder -v
```
