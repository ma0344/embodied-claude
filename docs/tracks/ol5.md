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
| **OL5-d** | close 照合 — `action_terms` の **head 展開**（`散歩に行く`→`散歩`） | ✅ 2026-06-29 | relationship-mcp `store.py` |
| **OL5-e** | loop **作成時** `what` → `action_terms[]` 正規化（head + 全文を保存） | 📋 | OL5-d とロジック共有 · **substring 路線の上限** |
| **OL5-f** | 作成時 e4b → `close_match_keys[]`（完了報告で出る短語列） | 📋 | OL5-c 拡張 or 同型1発 |
| **OL7** | **return-signal close** — `departure_context` + 合図発話を e4b で loop マップ | 📋 | [§ OL7](#ol7--return-signal-close設計-2026-06-29) |

**実装順（推奨）**: 現行維持 → **OL7**（e4b POC 済）→ OL5-f/e は必要なら · OL5-e 単独は優先低

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

**修正（2026-06-29）**: close 照合で `散歩に行く` 全文のみ要求し「散歩、行ってきた」が落ちる → **OL5-d** head 展開（`store._ol5_term_match_variants`）。作成時の `what` 正規化は **OL5-e**（📋）。

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

### 固有語（action_terms）— `what` からどう来るか

**e4b がやること**: 分類 + `what` / `object_phrase` / `action_phrase` の抽出。**専用の「固有語生成器」はない**（OL5-c は **completion_verbs のみ**）。

```
まーの発話
  ↓
TEMP-C Stage2（e4b）→ events[].what / action_phrase
  ↓
event_to_parsed — action_terms = (event.what,)  ※ what をそのまま1件
  ↓
merge_ol_gate_gateway → _normalize_action_terms
  ↓
apply_ol_gate_decision → detail_json.action_terms に保存
  ↓
close 時 — _ol5_loop_action_terms + _ol5_term_match_variants（OL5-d）で照合
```

| 段階 | 処理 | 例（散歩） |
|------|------|-----------|
| Stage2 `what` | プロンプトは名詞のみ指示 · 実際は e4b 任せ | `散歩に行く`（動詞混入あり） |
| `event_to_parsed` | **`what` を無加工で action_terms** | `["散歩に行く"]` |
| `_normalize_action_terms` | 末尾助詞だけ除去 `[をがはにでと]$` | `散歩に行く` → **変化なし** |
| close 照合（OL5-d） | 保存 term から head を展開してマッチ | `散歩` ∈ 「散歩、行ってきた」 ✅ |

**レガシー GW-S2 単発分類**（TEMP-C なし）: e4b JSON の `action_terms[]` を直接読む → 同じ `_normalize_action_terms` 通過。

**OL5-e（📋）**: 保存時に `what` から head を derive。**上限あり** — 「かにをゆでる」「はがきを買いに行く」は名詞+動詞の二部構成で substring/head だけでは弱い（→ **OL7**）。

**OL7（📋）**: e4b に **pending 行動への合図解釈**を任せる。表層の2ターン会話（認知→合図）を gateway ステートに落とす（下記 § OL7）。

### 既知ギャップ（2026-06-29 ma-home）

| 症状 | 原因 |
|------|------|
| 「終わったよ」だけでは close しない | OL5-b は loop 固有語 + 完了語を **1 発話**で要求 |
| 書類 loop が日跨ぎで消えない / 逆に消えてほしくない | topic に日付無し → stale 弱い · または **意図的に multi-day** なのに stale 対象 |
| 「散歩、行ってきた」で close しない | `action_terms=散歩に行く` の **全文 substring** 照合 | ✅ **OL5-d**（2026-06-29）· 📋 **OL7** |
| 「提出した」で close しない | seed が「作」系中心 | ✅ OL5-c · 📋 OL5-f keys |
| 「ただいま」「ゆでた」だけ | OL5-b は **同一発話に固有語+完了語**必須 · 会話文脈なし | 📋 **OL7** |
| 「はがきを買いに行く」等 | 固有語が名詞1語に定まらない | 📋 OL7 / OL5-f |

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
| **OL5-d** | close 照合 head 展開 | ✅ 2026-06-29 |
| **OL5-e / OL5-f** | 作成時 keys 正規化 | 📋 substring 上限 |
| **OL7** | return-signal · departure_context | 📋 POC 済 |

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

## OL7 — return-signal close（設計 · 2026-06-29）

**状態**: 📋 設計メモ（LM Studio 手動 POC 済 · gateway 未配線）

**きっかけ**: 現行 OL5-b は **毎 ingest 独立の substring 照合**。日本語は活動の言い方が一定でなく（名詞+動詞・「に行く」・合図のみ）、`what` コピー + `action_terms` では弱い。一方 **Gemma e4b** は **2ターンのステート**（認知 → 合図）で完了を繋げられる — 表層こよりが「伝わってるのに DB が閉じない」ギャップの説明になる。

**絶対原則（カレンダー GAPI-7b と同型）**: e4b は **どの loop を閉じるか**を返すだけ。**`status=closed` の実行は gateway**（`apply_ol_gate_decision` / 専用 close 経路）。表層の完了文は `completion_summary` 用で、DB close の根拠にしない。

横断原則: [Propose → Confirm → Execute](../architecture/llm-propose-confirm-execute.md) — **確認ステップを当たり前**に（一発 e4b 任せにしない）。

### 設計の芯 — 「Open Loop を閉じる機構」

OL7 の本体は **会話の1ターンで閉じる分類器**ではない。**open loop を DB で closed にする経路**である。

| 誤解しやすい焦点 | 本当の焦点 |
|------------------|------------|
| 1発話で正しく close できるか | **最終的に loop が閉じられるか** |
| 閾値・エッジの pass/fail | **閉じる / まだ閉じない / 確認してから閉じる** の経路設計 |
| 分類器のスコア | gateway が **いつ transaction close するか** |

**1ターン即 close もアリ · 確認のあと close もアリ。** 後者は OL6 と同型で、OL7 とも矛盾しない。

#### 例 — 複数ターンで閉じる（望ましい）

```
loop「散歩に行く」open
  まー: ただいま
  → OL7: 候補 loop_walk · confidence 中〜高だが即 close しない選択も可
  → こより: 散歩行ってきたん？
  → pending_check（OL6 と同型の pending · trigger=ol7_return_signal 可）
  まー: うん、気持ちよかった～
  → OL7 再判定 or OL6 短答ルール → loop_walk close（ol7_completion / ol6_completion）
```

「ただいま」単体では substring も弱いが、**確認1回で閉じられる**なら目的は達成。POC の 6/6 は **即 close 経路の可行性**の証拠であって、製品要件が「毎回1ターン」だとは限らない。

#### close 経路（案 · 排他ではない）

| 経路 | きっかけ | ターン数 |
|------|----------|----------|
| **OL5-b** | object + 完了語が同一発話 | 1 |
| **OL7 即 close** | 日本語検定型で候補が明確 · gateway が即実行を選ぶ | 1 |
| **OL7 → pending → close** | 合図はあるが曖昧 · こよりが自然確認 → 短答で close | 2+ |
| **OL6** | 予定時刻後の確認 →「終わったよ」 | 2+ |

`confidence` は **即 close するか / pending に回すか**のヒント。閾値未満＝永久に閉じない、ではない。

#### POC スクリプトとの関係

`scripts/ol7_classifier_poc.py` の PASS/FAIL は **分類器単体の回帰**用。製品の受け入れは「その発話で必ず close」ではなく **「適切な close 経路に乗るか」**（即 close · pending · no-op のいずれも正当）。

### LM Studio POC（まー · google/gemma-4-e4b · 2026-06-29）

**プロンプト骨子**（会話劇 — 分類器実装時は JSON に寄せる）:

1. 【認知】発言から「これから行うメインの行動」を特定 → 応援・送り出し
2. 【待機】戻りを待つ
3. 【合図】「戻った」「終わった」等 → 最初の行動を含む完了報告文を生成

#### POC A — 散歩 + 食事（複合）

| ターン | まー | e4b（要約） |
|--------|------|-------------|
| 1 | お昼ご飯を食べたあと散歩に行く | 行動特定 · いってらっしゃい |
| 2 | ただいま | **お昼ご飯を食べて、散歩に行ってきましたね** |

→ 「ただいま」だけで **複合行動全体**を完了にマップ。OL5-b では不可。

#### POC B — かに茹で（名詞+動詞 · 短い完了語）

| ターン | まー | e4b（要約） |
|--------|------|-------------|
| 1 | かにをゆでる | 作業特定 · いってらっしゃい |
| 2 | ゆでた | **カニを茹でてきましたね** |

→ 「ゆでた」だけで **かに** に紐づく完了。`action_terms=かにをゆでる` の substring では **「ゆでた」にかにもゆでも無い**。

#### POC C — 複数 pending（1:1 ではない · 2026-06-29）

**仮説**: POC A/B がうまくいったのは **開始1件↔終了1件** だからでは。同一チャットで **3行動を連続開始** して検証。

| # | まー（開始） | e4b |
|---|-------------|-----|
| 1 | お昼寝する | いってらっしゃい |
| 2 | 書類を作る | 頑張って（別タスクとして認知） |
| 3 | みかんを食べる | いってらっしゃい |

| # | まー（その後） | e4b | 判定 |
|---|---------------|-----|------|
| 4 | おはよう | 挨拶に切替（行動として認識しない） | ✅ 誤 close なし |
| 5 | 昼寝終わった | お昼寝を終わらせてきた | ✅ **明示完了**（object+終わった） |
| 6 | ごちそうさま | 「お食事を終えられた」— **みかんではない** | ❌ 曖昧合図の誤マップ |
| 7 | 書類できた | 書類を仕上げてきた | ✅ **明示完了**（object+できた） |

**読み取り**:

| ネック | 内容 |
|--------|------|
| **会話記憶 ≠ open loop スタック** | プロンプトは3件とも「送り出し」するが、**どれがまだ open か**をモデルは管理しない。チャット履歴は閉じた行動も全部残る。 |
| **1:1 に見えた成功** | POC A の「ただいま」・POC B の「ゆでた」は **直前に1件だけ** pending だったから通った可能性が高い。 |
| **明示完了は N 件でも強い** | 「昼寝終わった」「書類できた」は **OL5-b 同型**（object+完了語）— 複数 pending があっても当たりやすい。 |
| **曖昧合図は危険** | 「ごちそうさま」→ 食事フレームに吸い込まれ **みかん loop と不一致**。文化句・短い感謝は **どの loop か特定不能**。 |
| **会話劇プロンプトの限界** | 表層の「納得いく返答」と **DB の正確な1 loop close** は別問題。N>1 では drama だけでは足りない。 |

**OL7 への含意**（会話劇をそのまま載せない理由）:

1. e4b 入力は **チャット履歴ではなく `open_loops[]`（DB · status=open のみ）** を毎回注入
2. 出力は **JSON `close_loop_ids[]` + `confidence`** — gateway が **即 close / pending / no-op** を決める
3. **1発話で close するのは経路の一つ**（明示完了など）。合図だけのときは **確認ターン**へ回してよい
4. 「ごちそうさま」級は即 close しなくてよい · **聞き返し or 無視** — 閉じられなくても失敗ではない
5. **ハイブリッド順**: OL5-b（明示）→ OL7 判定 → 強ければ即 close · 弱ければ pending · 無ければ no-op

### 心象モデル — 「最もよい組み合わせ」の選択（日本語検定型）

OL7 の e4b タスクは **会話劇ではなく、選択問題に近い**:

> 次の言葉の使い方として最もよいものを選びなさい。  
> 「欠陥」  
> 1 この小説には登場人物が多すぎるという欠陥がある。  
> 2 テーブルの表面にはたくさんの欠陥がついていた。  
> 3 その製品は欠陥が見つかったために回収された。  
> 4 就職の面接で自分の欠陥を挙げるように言われた。

正解は **3**（製品 × 欠陥）。1・4 は **コロケーションが破綻**（文学・自分には 欠点/短所）。2 は文として弱い。

**OL7 への対応づけ**:

| 検定 | OL7 |
|------|-----|
| 穴埋め語「欠陥」 | 今回の発話（ごちそうさま · ただいま · 昼寝終わった） |
| 選択肢 1〜4 | `open_loops[]`（お昼寝する · 書類を作る · みかんを食べる …） |
| 最もよい組み合わせ | `close_loop_ids` に入れる **1件**（原則） |
| どれも不自然 | `close_loop_ids=[]` · `signal=none`（**「正解なし」も正当な出力**） |

| 発話 | 最良の組み合わせ | POC C の結果 |
|------|------------------|--------------|
| 昼寝終わった | loop「お昼寝する」 | ✅ 自然なコロケーション |
| 書類できた | loop「書類を作る」 | ✅ |
| ごちそうさま | **どの loop にも弱い**（みかんは「食事」枠に入りにくい） | ❌ 選択肢外の「お食事」を捏造 — **5番目の選択肢を勝手に作った** |
| おはよう | 完了合図として **全選択肢と不適合** | ✅ close しない |

**OL5-b との違い**: substring は「語が含まれるか」だけ。**OL7 は「この発話は、この departure とペアとして自然か」** — 日本語検定の **用法問題**と同型。

**実装含意**:

- プロンプトに **open_loops を番号付き選択肢**として列挙 · 「リスト外の行動を推測するな」
- `confidence` は gateway の **即 close vs pending** の材料（二値の品質ゲートではない）
- 表層こよりは別 LLM — **合わせて返答を作る**のと **どれを close するか選ぶ**のは分離（GAPI-7d 同型）
- **pending** は OL6 と共有スキーマ可（`trigger`: `ol7_return_signal` | `post_deadline_first_turn`）

### 現行方式との対比

| | OL5-b（現行） | OL7（案） |
|--|---------------|-----------|
| 記憶 | `detail_json.action_terms` | **`open_loops[]`（DB）** + `departure_context` |
| 「散歩、行ってきた」 | keys 照合（OL5-d で改善） | 合図 or 明示完了のどちらも可 |
| 「ただいま」「ゆでた」 | ほぼ不可 | **1:1 なら可 · N>1 は open 一覧必須** |
| 複合（食事→散歩） | loop 分割時は個別 close | **1合図で全 close は POC のみ · 本番は非推奨** |
| 明示（書類できた） | ✅ 既に強い | OL5-b 優先 · OL7 はフォールバック |
| 実行 | Python substring | gateway が `close_loop_ids[]` を close |

### ステート（gateway が persist）

```
【認知】future_commitment ingest
  → open loop 作成（現行 TEMP-C）
  → detail に departure_context を追加:
      { source_utterance, events_summary[], created_at }

【待機】 status=open

【合図・完了の ingest】毎ターン（stateless · open_loops[] 注入）:
  → e4b 日本語検定型 JSON:
      {
        "signal": "none | explicit_completion | return_signal",
        "close_loop_ids": ["loop_xxx", ...],
        "completion_summary": "...",
        "confidence": 0.0-1.0
      }
  → gateway 分岐:
      A) close_loop_ids あり & 即 close ポリシー → transaction close（ol7_completion）
      B) 候補あり & 確認が望ましい → pending_check 設定 · 表層が自然確認
      C) 候補なし → no-op（loop 維持）

【確認後 ingest】pending あり:
  → OL6 Stage3 同型（完了短答 / まだ / dismiss）
  → または OL7 再判定（2ターン目の文脈で confidence 上昇）
  → close → [open_loops_close_result] 注入（calendar 同型の正直化）
```

**チャット履歴は表層用** — close 判定の根拠は **`open_loops[]` + pending + 当該 utterance**（セッション跨ぎ · キオスク向け）。

### 他 OL との役割分担

| 経路 | きっかけ | 例 |
|------|----------|-----|
| **OL5-b** | 同一発話に object + 完了語 | 散歩、行ってきた |
| **OL5-f** | 作成時 keys + 完了語（e4b keys · substring） | かに、ゆでた（keys に かに・ゆで） |
| **OL6** | 予定時刻後 · こより確認 → 短答 | 終わったよ（書類） |
| **OL7** | **合図・用法マップ** → 即 close **または** pending → close | ただいま → 確認 → うん |

**ハイブリッド（推奨）**: OL5-b → OL7 判定 → **即 close | pending | no-op**。OL6 は **時刻トリガー**の確認 · pending 機構は共通化可。

### gateway 注入ブロック（案）

```
[open_loops_close_result]
status=ok
closed=loop_6ad91541b1
summary=散歩に行ってきた
[/open_loops_close_result]

[Gateway directive — not for the user]
Report closed loops ONLY from this block. Do NOT claim tasks are done without status=ok.
```

カレンダー `[calendar_write_result]` と同じパターンで口先完了を抑止。

### POC スクリプト（日本語検定型 · 2026-06-29）

```powershell
cd presence-ui
$env:PRESENCE_CLASSIFIER_MODEL = "google/gemma-4-e4b"
uv run python scripts/ol7_classifier_poc.py --case all
# poc_a | poc_b | poc_c
```

実装: `presence-ui/src/presence_ui/gateway/ol7_return_signal.py`（gateway 未配線 · classifier のみ）

**e4b 結果（分類器単体 · 即 close 経路の参考）**:

| case | 発話 | 分類器出力 | 製品での扱い（案） |
|------|------|------------|-------------------|
| poc_a | ただいま | loop_walk · 0.90 | 即 close **or** pending→確認 |
| poc_b | ゆでた | loop_crab · 0.95 | 即 close 可 |
| poc_c | おはよう | none | no-op |
| poc_c | 昼寝終わった | loop_nap | 即 close（OL5-b でも可） |
| poc_c | ごちそうさま | none | no-op · 必要なら別ターンで確認 |
| poc_c | 書類できた | loop_docs | 即 close |

### 実装タッチポイント（着手時）

| 層 | 内容 | 状態 |
|----|------|------|
| `relationship-mcp` | `set_ol7_pending_candidate` · `close_open_loops_by_ids` · shared `pending_check` | ✅ |
| `social_core/ol6_check` | `is_pending_completion_confirm` · `PENDING_TRIGGER_OL7` | ✅ |
| `presence_ui/gateway/ol7_flow.py` | ingest: 即 close / pending / no-op | ✅（`PRESENCE_OL7_ENABLED=1`） |
| `compose` / `plan` | `loops_due_for_check` に OL7 trigger · followup | ✅ |
| `heartbeat/record.py` | `mark_loop_check_asked(trigger=…)` | ✅ |
| `social_chat.py` | `[open_loops_close_result]` 注入 | 📋 |
| env | `PRESENCE_OL7_ENABLED=0` · `PRESENCE_OL7_IMMEDIATE_CONFIDENCE=0.9` | |

**共有 pending フロー**（`trigger=ol7_return_signal`）:

```
ingest「ただいま」→ OL7 pending_candidate（asked_at なし）
→ compose/plan → こより「散歩行ってきたん？」
→ record → mark_loop_check_asked（asked_at 設定）
→ ingest「うん、気持ちよかった」→ try_ol6_pending_close（close_kind=ol7_completion）
```

### リスク・未決

| 項目 | メモ |
|------|------|
| **N>1 pending** | open 一覧注入は必須 · 即 close できなくても pending で救える |
| 誤 close | **即 close 経路**だけ厳しめ · 曖昧は pending or no-op |
| pending 統合 | OL6 `pending_check` を OL7 トリガーでも再利用するか |
| 明示完了 | 「書類できた」系は **OL5-b を先に** |
| e4b コスト | open loop あり & OL5 miss のとき |
| プロンプト | JSON 分類器 + **open_loops[] only** · 会話劇は表層のみ |

### 受け入れテスト（着手時）

**即 close**

1. loop「散歩に行く」1件 →「ただいま」→ 即 close **または** pending（どちらも可）
2. loop「かにをゆでる」→「ゆでた」→ closed
3. 3件 open →「昼寝終わった」→ **昼寝のみ** closed

**確認経路（2+ ターン）**

4. loop「散歩に行く」→「ただいま」→ こより確認 →「うん、いい感じ」→ closed
5. 「ごちそうさま」（みかん open）→ 即 close しない → 必要なら「みかん食べたん？」→ 短答で close

**no-op / 他経路**

6. 「おはよう」（open あり）→ close しない
7. 「散歩、行ってきた」→ OL5-b · OL7 不要
8. e4b 失敗 → open 維持 · 表層に success 宣言させない

---

## 次の確認

**朝（2026-06-30）**: [OL Close 朝テスト](./ops/ol7-morning-close-test.md) → 通ったら **TEMP-C5**

1. ~~実発話（「行ってきた」「作った」）で open loop が **closed** になるか~~ ✅
2. GW-S2 ON で phatic 挨拶が loop にならないか
3. **TEMP-C4** 後 — `resolved_date` 付き loop の stale が意図どおりか
4. **OL5-c** — 「提出した」で書類 loop が close するか
5. **OL6** — 確認 →「終わったよ」で close するか
6. **OL-STALE** — exempt loop が日跨ぎで open のまま · OL5/OL6/dismiss では閉じるか
7. **OL7** — [朝テスト runbook](./ops/ol7-morning-close-test.md)（即 close · ただいま→確認→短答）
8. **TEMP-C5** — `この後 午前2時` → `start_at`（Close テスト後）

```powershell
cd presence-ui
uv pip install --reinstall "relationship-mcp @ file:///C:/Users/ma/src/embodied-claude/sociality-mcp/packages/relationship-mcp"
.\scripts\restart-presence-ui.ps1
```
