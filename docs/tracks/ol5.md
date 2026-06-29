# OL5 — 予定消化で open loop 終了

**状態**: ✅ OL5-a/b/c/6 運用確認済 · ✅ **OL-STALE**（2026-06-29 v1）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [architecture/open-loops-reminders.md](../architecture/open-loops-reminders.md)、[gw-silent.md](./gw-silent.md)、[utterance-anchoring.md](./utterance-anchoring.md)（TEMP-C4）

---

## ロードマップ（合意 2026-06-29）

| ID | 内容 | 状態 | 依存 |
|----|------|------|------|
| **OL5-a** | 作成時 `completion_verbs[]` ヒューリスティック seed | ✅ | — |
| **OL5-b** | ingest `past_completion` + union close | ✅ | GW-S2 |
| **OL5-c** | classifier（e4b）で **topic 別完了語セット**生成（seed より広い） | ✅ 2026-06-29 | PFC-1 ✅ |
| **OL6** | **会話文脈付き close** — **予定時刻後の最初の会話**で自然確認 →「終わったよ」で loop 閉じ | ✅ 2026-06-29 | compose/plan · ingest · `until_phrase` |
| **OL-STALE** | **日跨ぎで閉じない** loop のルート（`stale_policy`） | ✅ 2026-06-29 v1 | TEMP-C4 ✅ |
| **TEMP-C4** | loop 作成時 **`resolved_date` / when 継承**の固定 | ✅ 2026-06-29 | TEMP-C3 ✅ |

**実装順（推奨）**: TEMP-C4 → OL5-c → OL6 → OL-STALE（C4 で stale の当たり外れを減らしてから exempt を足す）。

---

## 現状

| 層 | 内容 | 状態 |
|----|------|------|
| **作成** | GW-S2 OL-GATE — When / What / How が揃うときだけ loop | ✅（`PRESENCE_GW_S2_ENABLED=1`） |
| **seed** | loop 作成時に `completion_verbs[]` を `detail_json` へ | ✅ OL5-a（ヒューリスティック、`action_phrase` から） |
| **close** | ingest 再解析 `past_completion` + 保存 verbs の union 照合 | ✅ 運用確認済 |
| **fallback** | カレンダー日跨ぎ `close_stale_open_loops` | ✅ 従来どおり |

**ma-home 確認（2026-06-25）**: `list_open_loops` の `detail.completion_verbs` に例 `["行ってきた", "行った", "出かけてきた"]` が載ることを確認。

**ma-home 確認（2026-06-27）**: ingest「ちょっと早かったけど、ライブ、行ってきた」で loop `loop_ea4dbebeb3`（topic: 2026年6月27日、18:00にライブに行く）が `status=closed`、`detail_json.kind=ol5_completion`。

**修正（2026-06-27）**: ingest の `action_terms` を全 open loop に union していたため、ライブ close で肉じゃが loop も誤 close した → loop 固有 term のみ照合に変更（`0aa773e`）。

**作成側（v0 残）**: GW-S2 OFF 時は **いつ** だけで loop ができる（「また明日！」→ phatic loop）。本番は GW-S2 ON 推奨。

---

## 望ましい将来

予定 **消化** を発話や experience から検知 → 関連 topic の loop を close。

| 例 | v0（日跨ぎのみ） | OL5 後 |
|----|-----------------|--------|
| 角煮を作る | 日跨ぎまで open | 「角煮、作った」で close |
| 明日朝散歩 | 日跨ぎまで open | 「散歩行ってきた」で close |

---

## 設計要点

- dismiss（「忘れて」）とは別 — **成功完了**の肯定閉じ
- **完了フレーズはタスク依存（動的）**: topic から活動の核 + その活動に自然な完了表現
- **セット照合（OL5-b）**: 行動語 + 完了語が **同一 ingest 発話**に両方（「作った」単体では不可）
- **会話ターン跨ぎ（OL6）**: ✅ 予定時刻後の確認 →「終わったよ」close
- **日跨ぎ stale（OL-STALE）**: ✅ `stale_policy` — default は日跨ぎ close · `until_completed` は exempt

### 既知ギャップ（2026-06-29 ma-home）

| 症状 | 原因 |
|------|------|
| 「終わったよ」だけでは close しない | OL5-b は loop 固有語 + 完了語を **1 発話**で要求 |
| 書類 loop が日跨ぎで消えない / 逆に消えてほしくない | topic に日付無し → stale 弱い · または **意図的に multi-day** なのに stale 対象 |
| 「提出した」で close しない | OL5-a seed が「作」系中心（OL5-c で拡張予定） |

---

## 実装段階

| 段階 | 内容 | 状態 |
|------|------|------|
| v0 | 日跨ぎ stale のみ | ✅ |
| **OL5-a** | 作成時 `completion_verbs` ヒューリスティック seed | ✅ 2026-06-25 |
| **OL5-b** | ingest `past_completion` 再解析 + union close | ✅ 2026-06-27 運用確認 |
| **OL5-c** | classifier（e4b）で LLM 完了語セット生成 | ✅ 2026-06-29 |
| **OL6** | pending loop check → 文脈付き close | ✅ 2026-06-29 |
| **OL-STALE** | `stale_policy` · 日跨ぎ exempt ルート | ✅ 2026-06-29 v1 |

LM Studio 手動テスト（Gemma）で「散歩に行く」→ 完了フレーズ 10 個生成は **ルール単語リストより topic 展開が現実的** という根拠あり。詳細例は [archive/backlog-ma-home-full-2026-06-26.md](../archive/backlog-ma-home-full-2026-06-26.md) § OL5。

---

## OL5-c — LLM 完了語 seed（✅ 2026-06-29）

**目的**: OL5-a の stem ルール（作/行/食べ…）では拾えない完了表現を loop 作成時に載せる。

| 例 | OL5-a seed | OL5-c で足したい |
|----|------------|------------------|
| 県に提出する書類 | 作った / できた / 完成した | **提出した / 送った / 出した** |
| 散歩に行く | 行ってきた / 行った | そのまま + 口語揺れ |

**呼び出し**:

- **モデル**: `PRESENCE_CLASSIFIER_MODEL`（e4b）— 表層 12B KV を汚さない
- **タイミング**: open loop **作成直後**（Stage3 `apply_ol_gate_decision` 前後）· stateless JSON
- **入力**: `loop_topic`, `object_phrase`, `action_phrase`, `event.what`
- **出力**: `completion_verbs[]`（最大 8–10 · 過去形・口語）

**保存**: `detail_json.completion_verbs` を OL5-a seed と **merge**（union · 上限 10）。

**close 照合**: OL5-b と同じ — ingest `past_completion` 時に stored ∪ ingest verbs。

**実装**: `presence_ui/gateway/ol5_completion_verbs.py` — `enrich_decision_completion_verbs` を staged / legacy ingest 経路で loop 作成直前に呼ぶ。失敗時 OL5-a seed のみ。

**env**: `PRESENCE_OL5_C_ENABLED=1`（既定 ON）· `PRESENCE_OL5_C_MAX_TOKENS=280`

---

## OL6 — 会話文脈付き loop close（✅ 2026-06-29）

**きっかけ（2026-06-29 · ma-home 合意）**: 現状は表層 LLM の**気まぐれ**に確認が乗るだけ。望ましいのは **`until_phrase` / 予定終了時刻を過ぎたあと、最初の人間との会話**で、こよりが自然に「掃除、終わった？」「書類、どう？」と聞くこと。まーが「終わったよ」と答えたら loop close（OL5-b 単体では不可な短答を救う）。

**例**: loop「10時ごろまで部屋の掃除」→ 10:00 以降 **初回** compose/plan → 短い確認 → pending → ingest「終わったよ」→ **ol6_completion** close。

**ma-home 運用確認（2026-06-29 10:03）**: 上記フロー通り — 「部屋の掃除はもう終わったん？」→「終わったよ」→ DB closed。

### 望ましいフロー

```
loop 作成（detail: until_phrase, resolved_date, completion_verbs）
     ↓
as_of > 予定終了時刻（パース or ヒューリスティック）
  AND status=open
  AND check_asked_at 未設定（同一 loop で1回だけ）
     ↓
compose — loops_due_for_check[] を context に載せる
     ↓
plan — must_include: 自然な確認（1 loop · 押し付けない · 本題があれば後回し可）
     ↓
表層が確認を出す → record_agent_experience（kind: loop_check_asked, loop_id）
     ↓
detail.pending_check または experience から pending 化
     ↓
次 human ingest → Stage3 が pending_loop_check を参照
     ↓
「終わったよ / まだ / 忘れて」等をルーティング
     ↓
close（ol6_completion）| 維持 | dismiss
```

**OL5-b との棲み分け**:

| 経路 | きっかけ | 例 |
|------|----------|-----|
| **OL5-b** | 同一発話に loop 固有語 + 完了語 | 「散歩、行ってきた」 |
| **OL6** | 予定時刻後の確認 → 短答 | 「書類、終わった？」→「終わったよ」 |

### トリガー（案 · 決定的）

| 条件 | 意味 |
|------|------|
| `status=open` | 未 close |
| `detail.until_phrase` または topic/anchor から **終了時刻**を推定 | 「10時まで」「15時くらいまで」 |
| `resolved_date` + tz で **終了 datetime** を計算 | TEMP-C4 の anchor を再利用 |
| `now > end_dt` | 予定時間を過ぎた |
| `detail.check_asked_at` が null | **この loop ではまだ確認してない** |
| **人間発話ターン**（挨拶含む） | 自律 tick だけでは聞かない（v1） |

→ **LLM の気まぐれではなく compose/plan のルール**で「聞くべき loop」を決める。表層は言い回しだけ担当。

**優先**: 複数 due なら **最も古く過ぎた1件**から（または until が最も近い過去1件）。全部一度に聞かない。

### データ（案）

**`agent_experiences`** または **`open_loops.detail_json.pending_check`**:

| フィールド | 意味 |
|------------|------|
| `loop_id` | 確認対象 |
| `asked_at` | ISO ts（= `detail.check_asked_at` に mirror 可） |
| `expires_after_sec` | 例 3600 — 古い pending は無視 |
| `ask_snippet` | 「書類、もう終わった？」 |
| `trigger` | `post_deadline_first_turn`（OL6 既定） |

### Stage3 ルール（案）

| human 発話パターン | 判定 | 動作 |
|--------------------|------|------|
| pending あり + **完了系短答**（終わった / できた / 済んだ / もういい完了意味） | `completion_confirm` | 対象 loop を **ol6_completion** で close |
| pending あり + **未完了**（まだ / これから） | — | pending クリア · loop 維持 |
| pending あり + **dismiss** | dismiss | 既存 dismiss 経路 |
| pending なし | — | 現行 OL5-b のみ |

**OL5-b との関係**: OL6 は **pending があるターンだけ** 固有語なし完了を許可。それ以外は OL5-b の厳密照合を維持。

### plan 側（案）

- compose が **`loops_due_for_check`**（`loop_id` · topic · until 要約）を載せる
- plan `must_include`: 「post-deadline loop — 自然に短く確認してよい（1件）」— **任意ではなく due 時は推奨**（本題ターンでは1文に添える程度）
- 確認したら `record_agent_experience` + **`detail.check_asked_at`** を必ず書く（**書かないと OL6 ingest が効かない · 二重確認防止**）

### 実装タッチポイント

| 層 | ファイル（想定） |
|----|------------------|
| 時刻判定 | `social_core.date_resolution` — `until_phrase` + `resolved_date` → end_dt |
| compose | `compose.py` — `loops_due_for_check` · open loop detail 露出 |
| plan | `plan.py` — post-deadline `must_include` |
| 記録 | `record_agent_experience` kind `loop_check_asked` · `relationship_mcp` `check_asked_at` |
| ingest | `temp_c_staged.py` / `ol_gate.py` — pending 参照して close |

---

## OL-STALE — 日跨ぎで閉じない loop（✅ 2026-06-29 v1）

**関連**: [open-loops-reminders.md § OL-STALE](../architecture/open-loops-reminders.md#ol-stale--日跨ぎで閉じない-loop)

**v1 実装**: `social_core/ol_stale.py` — `stale_policy`（`default` / `until_completed` / `until_date`）· `close_stale_open_loops` が exempt を skip · 作成時 `resolved_date` なし → `until_completed` · 明示 cue（「終わるまで」等）も `until_completed`。

**きっかけ**:

- **消えてほしくない**: 書類作成など **複数日** · 具体日が無い · 「終わるまで覚えて」
- **消えてほしい**: 「明日の角煮」— `resolved_date` 翌日で stale close（現行どおり）

**原則**: stale close は **デフォルト ON**。exempt は **明示ルート**でのみ。

---

## 次の確認

1. ~~実発話（「行ってきた」「作った」）で open loop が **closed** になるか~~ ✅
2. GW-S2 ON で phatic 挨拶が loop にならないか
3. **TEMP-C4** 後 — `resolved_date` 付き loop の stale が意図どおりか
4. **OL5-c** — 「提出した」で書類 loop が close するか
5. **OL6** — 確認 →「終わったよ」で close するか
6. **OL-STALE** — exempt loop が日跨ぎで open のまま · OL5/OL6/dismiss では閉じるか

```powershell
cd presence-ui
uv pip install --reinstall "relationship-mcp @ file:///C:/Users/ma/src/embodied-claude/sociality-mcp/packages/relationship-mcp"
.\scripts\restart-presence-ui.ps1
```
