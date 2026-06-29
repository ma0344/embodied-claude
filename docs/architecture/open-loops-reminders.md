# Open Loops / リマインド（OL1 + OL2）

**実装**: 2026-06-16  
**関連**: [cognitive-layers.md](./cognitive-layers.md)、[gateway-direct-actions.md](./gateway-direct-actions.md)、[backlog-ma-home.md](../backlog-ma-home.md)

---

## 何が動くか

### OL1 — 日付解決

- ingest 時に open loop の `detail_json.resolved_date`（`明日` / `今日` / `明後日` → JST カレンダー日）
- **OL1b（2026-06-19）**: 保存時に相対日を **具体日**（`2026年6月19日`）へ置換 — open loop `topic`、STM `summary`、`agent_experiences.summary`。`original_topic` は `detail_json` に残す。compose 先頭に `Calendar today (Asia/Tokyo): …`
- **OL1c（2026-06-19）**: 日曜始まりの週界 + 曜日 lookup（コードのみ）— `来週の火曜` / `再来週の月曜` / `一週間後` / `N日後` / `来月の頭` / `今週末` / `6月20日` など
- **OL2（temporal）（2026-06-19）**: `次の{曜}` / `今度の{曜}`（同義・次に来るその曜日）、`来週中` 等の曖昧スパンはアンカーせず `needs_date_confirmation` → compose `[date_confirmation_needed]` / plan `must_include` でまーに聞く。`social_core.ja_timex_bridge`（任意・PoC/ベンチ用）
- 期限切れ loop は ingest / 自律 tick 前の `close_stale_open_loops` で `status=closed`（アンカー後は `resolved_date` でも判定）
- **OL5-a/b**: 予定消化（作った/できた）でも loop close — [tracks/ol5.md](../tracks/ol5.md) ✅
- **OL5-c / OL6 / OL-STALE**: ✅ — [tracks/ol5.md](../tracks/ol5.md)
- 手動掃除: `scripts/purge-stale-open-loops.py`（共有ロジックは `social_core.date_resolution`）

**横断（2026-06-28）**: open loop 以外の inject（interpretation_shift · dream_digest · memory recall）でも **uttered_at + resolved_date + as_of** が必要 → [tracks/utterance-anchoring.md](../tracks/utterance-anchoring.md)（TEMP）。OL2 の `resolved_date` / stale パターンがテンプレート。

### OL2 — リマインド

1. 部屋で「10時に〇〇をリマインドして」等 → `create_commitment(due_at)`（`reminder_intent.py`）
2. **Phase B**: ルールで `due_at` が取れないがリマインド意図がある発話 → Gateway が LM Studio で JSON spec を **登録時に1回だけ** 生成 → `create_reminder_from_spec(source=reminder_llm)`（`PRESENCE_LLM_REMINDER_SPEC=1` 既定、0 で無効）
3. compose が `list_due_commitments` で `[commitments_due]` を注入（旧 `person_model.commitments` バグ修正済み）
   - **注意**: `list_due_commitments` は **due_at を過ぎた** active のみ（未来の 16:30 リマインドは compose に出ない）。発火は reminder watchdog / 自律 tick。
4. **reminder watchdog**（60s）または 15m 自律 tick: `remind_commitment_direct`（`speak_line` 固定、LLM なし）→ outbound + `room_say`

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

## OL-GATE — loop 作成条件（設計メモ、合意 2026-06-26）

**あるべき条件**: **いつ**・**何を**・**どうする** がはっきり揃ったときだけ open loop にする — いわば会話から抜き出す **5W1H のうち When / What / How**（IBF のコミュニケーションモデルと同型 → [intent-bucket-flow.md § 5W1H](./intent-bucket-flow.md#5w1h-と覚えておくべきこと合意-2026-06-26)）。

| 要素 | 例 | いま |
|------|-----|------|
| **いつ** | 明日、来週火曜、9:30 | ✅ GW-S2 または v0 `FUTURE_MARKERS` |
| **何を** | 角煮、会議、散歩、PR review | ✅ GW-S2 `object_phrase`（opt-in） |
| **どうする** | 作る、行く、連絡する、リマインド | ✅ GW-S2 `action_phrase`（opt-in） |

**現状（v0、GW-S2 OFF）**: `relationship_mcp/inference.py` の `FUTURE_MARKERS` が **いつ** だけで `_extract_topic` が通る → loop 作成。  
→ 「また明日！」のような **挨拶（phatic）** も「また2026年6月27日！」loop になる。

**現状（v1、GW-S2 ON）**: ingest 後分類器で When / What / How を抽出。phatic は loop なし。`list_open_loops.detail` で W/W/H と `completion_verbs` を確認可。

**方針**: 否定的リスト（「また明日」を禁止）は **よほどの再発例がなければ作らない**。

**v1（ルール）**: **いつ AND 行動の核** — 時間マーカーに加え、タスク名詞・動作語・引用句のいずれかが同じ発話にあるときだけ loop。

```
loop を作る ⇔ has_temporal_anchor(text) AND has_action_nucleus(text)
```

行動の核の族: 作る/行く/やる/連絡/確認…、会議・散歩・角煮…、「覚えといて」+ 中身（MEM-8f と役割分担）。

**v2（GW-S2）**: ingest 後の黙考で **推測なし** に temporal / object / action を抜き出し → `is_follow_up_task` → gateway が `create_open_loop` を決める。

手動スモーク v2（Gemma 4-12b-qat, 2026-06-26）— 4 例すべて期待どおり:

| 例文 | `is_follow_up_task` | loop |
|------|---------------------|------|
| いつも一緒にいたかった | false | なし（願望） |
| 明日、角煮を作る | true | **あり**（+ `is_future_commitment`） |
| 昨日、ロバがコケた | true | なし（過去 → remember 側） |
| また明日！ | false | なし（phatic） |

→ [gw-silent.md § GW-S2](../tracks/gw-silent.md#gw-s2--ol-gatewhen--what--how-抽出)

LLM 出力（抜粋）:

```json
{
  "temporal_phrase": "明日",
  "object_phrase": "角煮を",
  "action_phrase": "作る",
  "is_follow_up_task": true,
  "ineligibility_reason": null
}
```

Gateway: `create_open_loop = utterance_kind == future_commitment && object && action && is_future_commitment`。**v3 スモーク**で 3 スロット一律では **完了報告（角煮作った）が弾かれる** → `utterance_kind` 必須。→ [gw-silent.md § v3](../tracks/gw-silent.md#検討--utterance_kind-三分類v3-スモークで推奨度)

ルール v1 で足りる例はルールのまま。**境界・曖昧**だけ GW（IBF-7 と同型ハイブリッド）。

**close 側（OL5）**: 作成ゲートと対になる — 消化時も **何を + どうした** のセット照合（日跨ぎ stale だけに頼らない）。

**実装（2026-06-25）**: GW-S2 + OL5-a/b 配線済。`completion_verbs` は作成時 seed、close は ingest `past_completion` と union。本番 ON: `PRESENCE_GW_S2_ENABLED=1` + `presence-ui` venv へ `relationship-mcp` reinstall。

---

## OL-STALE — 日跨ぎで閉じない loop

**状態**: 📋 計画（2026-06-29 合意）· ✅ **v1 実装**（2026-06-29）  
**関連**: [ol5.md § OL-STALE](../tracks/ol5.md#ol-stale--日跨ぎで閉じない-loop計画) · [utterance-anchoring.md § TEMP-C4](../tracks/utterance-anchoring.md#temp-c4--open-loop-アンカー計画)

### 現状

`close_stale_open_loops`（ingest / tick 前）は **原則すべての open loop** を対象:

- topic / `detail.resolved_date` からカレンダー日を解決
- **その日を過ぎたら** `status=closed`（`kind=stale`）

**問題例**:

| loop | 望み | 現状 |
|------|------|------|
| 明日の角煮 | 6/29 終了後に stale close | ✅ 意図どおり（TEMP-C4 で `resolved_date` 安定後） |
| 県に提出する書類（日付なし） | 終わるまで open | stale **効かない** · OL5 も弱い |
| 来週までの書類 | 来週まで open | 誤って **明日扱い** anchor されると翌日 close — **避けたい** |

### `stale_policy`（案）

loop 作成時または訂正 ingest で `detail_json` に載せる:

| 値 | 意味 | stale | close 経路 |
|----|------|-------|------------|
| `default`（省略時） | 単日予定 | ✅ 日跨ぎ close | OL5 · dismiss · OL6 |
| `until_completed` | 完了まで日跨ぎ OK | ❌ skip | **OL5 / OL6 / dismiss のみ** |
| `until_date` | 明示期限まで | `stale_after` ISO 日まで skip | 期限日翌日から stale |

### ルート一覧 — 「日跨ぎで終了しないでほしい」とき

| ID | ルート | きっかけ（例） | Stage / 層 | 結果 |
|----|--------|----------------|------------|------|
| **OL-STALE-1** | **作成時 — 曖昧スパン** | 「来週中」「そのうち」 | OL2 既存 — `needs_date_confirmation` · loop **作らない or 日付確定まで保留** | stale 問題を未然に防ぐ |
| **OL-STALE-2** | **作成時 — multi-day 明示** | 「終わるまで覚えて」「日跨いでも」 | Stage2 将来フィールド `persistence: multi_day` または Stage3 ヒューリスティック | `stale_policy=until_completed` |
| **OL-STALE-3** | **訂正 ingest** | 「書類は明日で終わりじゃない」 | SHIFT-R `correction` → `schedule` / 新 `persistence` ルート | policy 更新 · `resolved_date` クリア or 延長 |
| **OL-STALE-4** | **dismiss ではない継続** | 「忘れないで」（dismiss 反対） | boundary / rule shift · または OL-STALE-2 と同型 | exempt 付与 |
| **OL-STALE-5** | **再 anchor** | 「来週の金曜まで」 | correction `schedule` · TEMP anchor | `until_date` + `stale_after` 設定 → その日まで open |
| **OL-STALE-6** | **手動 / 運用** | DB · script | `detail_json.stale_policy` 直接 · 将来 UI | 緊急用 |

**dismiss（忘れて）との違い**: dismiss = **もう追わない**（closed）。OL-STALE = **追い続けるが日跨ぎでは消さない**。

### close 経路の全体像（計画後）

```
                    ┌─ OL5-b (past_completion + 固有語+完了語)
                    ├─ OL5-c (広い completion_verbs)
open loop ─ close ─┼─ OL6 (pending 確認 →「終わったよ」)
                    ├─ dismiss / correction dismiss_topic
                    └─ stale (default policy のみ · resolved_date 翌日)
                         ↑ until_completed / until_date は skip
```

### 実装タッチポイント（案）

| 変更 | 場所 |
|------|------|
| `stale_policy` 読み取り | `relationship_mcp/store.py` — `close_stale_open_loops` · `apply_ol_gate_decision` |
| 作成時付与 | `temp_c_staged.py` Stage3 · `merge_ol_gate_gateway` detail |
| 訂正 | `correction_routing.py` — `schedule` / 新 target `persistence` |
| compose 表示 | `[open_loops]` に `(ongoing)` 等 — 表層が OL6 確認しやすく |

**TEMP-C4 との関係**: C4 で **単日** loop に `resolved_date` を確実に付ける → **default** の stale が正しく効く。exempt は **意図的に multi-day** なものだけ。

---

## 残リスク・既知の制限（運用メモ）

| 項目 | 内容 | 対策 |
|------|------|------|
| **relationship-mcp の reinstall 忘れ** | 古い venv だと `list_due_commitments` が無く、`commitments_due` が常に空 → リマインドが鳴らない | 上記デプロイ手順。コード変更のたびに `uv pip install --reinstall` + restart |
| **リマインド文面** | Phase A: ルールで `「…」`→`speak_line`。Phase B: ルール失敗時のみ Gateway LLM が JSON spec を 1 回生成（`PRESENCE_LLM_REMINDER_SPEC=1`） | 鳴るときは常に保存 `speak_line`（LLM なし） |
| **`N分後`** | `10分後に…教えて` / `say でしゃべって` をパース（全角数字対応） | 曖昧な相対表現は未対応 |
| **時刻精度** | Windows タスクは **15分間隔**（18:26 → 次 18:41）。`3分後` は最大 ~15分遅れ | presence-ui **reminder watchdog**（既定60秒、`PRESENCE_REMINDER_POLL_SEC`） |
| **音声（Surface）** | `room_inbound` のみだと SSE 切断時に無音。MCP `say` 経路と別 | `room_say` SSE + **poll フォールバック**（`/api/v1/tts/room-say/pending`） |
| **当日の相対日** | `明日` loop は **会議当日は open のまま**（`include_today=false`）。当日終了後に auto-close | 当日中に閉じたいときは `purge-stale-open-loops.py --include-today` |
| **multi-day / 日付なし loop** | stale が効かない or 意図とずれる | **OL-STALE** · **TEMP-C4** — 上記 § OL-STALE |
| **確認→「終わったよ」** | OL5-b 単体では close しない | **OL6 ✅** — 予定時刻後 **初回会話**で確認 → [ol5.md](../tracks/ol5.md) |

---

## コード参照

| モジュール | 役割 |
|-----------|------|
| `relationship_mcp/date_resolution.py` | 相対日付 → `date` |
| `relationship_mcp/reminder_intent.py` | 発話 → `ReminderSpec`（title / due_at / speak_line / delivery） |
| `relationship_mcp/store.py` | ingest / `list_due_commitments` / `close_stale_open_loops` |
| `interaction_orchestrator_mcp/compose.py` | `[commitments_due]` |
| `interaction_orchestrator_mcp/plan.py` | 自律時 commitment 優先 |
| `presence_ui/gateway/reminder_spec.py` | Phase B — LLM `generate_reminder_spec`（ルール失敗時のみ） |
| `presence_ui/gateway/reminder_watchdog.py` | 60s poll で due commitment を発火 |
| `presence_ui/gateway/autonomous_tick.py` | tick 前 stale 掃除 |

---

## テスト

```powershell
cd sociality-mcp/packages/relationship-mcp
uv run pytest tests/test_open_loops_reminders.py -v

cd ../interaction-orchestrator-mcp
uv sync --extra dev --reinstall-package relationship-mcp
uv run pytest tests/test_orchestrator.py::TestPlan::test_due_commitments_prioritize_autonomous_reminder -v

cd ../../../presence-ui
uv sync --extra dev --reinstall-package relationship-mcp
uv run python -m pytest tests/test_reminder_spec.py tests/test_room_ingest.py -v
```
