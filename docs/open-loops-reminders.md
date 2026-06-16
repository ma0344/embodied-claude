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
| **リマインド文面** | 固定テンプレ（例: 「まー、{text} の時間やで」）。LLM 生成は未接続 | 将来 `generate_koyori_reply` を `remind_commitment_direct` に載せる余地あり |
| **`grace_minutes`** | API 引数はあるが、現状は **24h catch-up**（`catch_up_hours`）のみで期限切れ commitment を拾う。狭い grace 窓は未使用 | tick 間隔（15m）と catch-up で実運用。必要なら `list_due_commitments` を絞る |
| **時刻パース** | 日本語の「N時にリマインド」「明日の10時」中心。英語・曖昧表現は未対応 | 失敗時は commitment が作られないだけ（既存 loop は維持） |
| **当日の相対日** | `明日` loop は **会議当日は open のまま**（`include_today=false`）。当日終了後に auto-close | 当日中に閉じたいときは `purge-stale-open-loops.py --include-today` |

---

## コード参照

| モジュール | 役割 |
|-----------|------|
| `relationship_mcp/date_resolution.py` | 相対日付 → `date` |
| `relationship_mcp/reminder_intent.py` | 発話 → `(label, due_at_iso)` |
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
