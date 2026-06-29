# TEMP — Utterance anchoring（相対日・deixis）

**状態**: 📋 TEMP-1/2/3/4 ✅ · TEMP-C3 ✅（要 `PRESENCE_GW_S2_STAGED=1`）  
**プロトタイプ**: [prottypemarkdown.md](../../prottypemarkdown.md)（Stage 1/2 プロンプト）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [open-loops-reminders.md](../architecture/open-loops-reminders.md)（OL2 · `resolved_date`）、[mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)、[tracks/gapi.md](./gapi.md)、[memory_context.py](../../presence-ui/src/presence_ui/services/memory_context.py)（morning fence）、[interpretation-shift-routing.md](./interpretation-shift-routing.md)（shift 追記条件 · TEMP-4 後）

---

## きっかけ（2026-06-28 — ma-home）

6/28 朝、まーが「おはよ」だけ言ったのに、こよりが **6/27 の「今日は入浴介助…角煮…」** を **6/28 の予定** として復唱した。

注入ブロック上の出どころは **GAPI / カレンダーではない** — `interpretation_shift` · `relevant_memories` · `dream_digest`（6/27 ラベル付き）· `recent_experiences`。`calendar_anchor_line` は「いま何月何日か」だけ。

**中核**: 相対日（**今日 / 明日 / 明後日 / 3日後**）は **発話単体では意味を持たない**。「**その会話がいつのものか**」（`uttered_at`）と **読む日**（`as_of`）がないと、昨日の「今日」が今日にすり替わる。

**6/28 のバグの正体**: 「おはよ」に予定を **触れてはいけない** のではなく、**権威のない経路**（stale `interpretation_shift` · `dream_digest` · 昨日 episode）から **昨日の「今日」を今日の予定として復唱した**こと。正しい今日の予定は **`[open_loops]`**（`resolved_date == as_of`）が authoritative — 朝の挨拶で短く触れてよい（推奨）。

---

## 朝の挨拶 — 幽霊禁止 vs open_loops（合意 2026-06-29）

| ソース | 「おはよ」/「今日の予定？」での扱い |
|--------|-------------------------------------|
| **`[open_loops]`**（`resolved_date == as_of` · status=open） | ✅ **正** — 短く触れてよい。**欠落**（幽霊より）の方が問題 |
| **stale `interpretation_shift`** | ❌ inject しない（TEMP-2）· 表層でも言わない |
| **`dream_digest` / recall / 昨日 episode** | ❌ 予定として言わない（TEMP-5 対象） |
| **GAPI calendar** | 接続時は calendar · 未接続時は open_loops のみ |

**6/29 朝の検証例**（open_loops = お昼→書類 / 散歩 / 書類15時まで · 掃除 loop は手動 close 済）:

| ターン | 観測 | 判定 |
|--------|------|------|
| 「おはよ」 | 書類・散歩に触れた · 15時ブロックは薄い | 幽霊なし · **open_loops の網羅が弱い** |
| 「今日の予定ってどんなだっけ？」 | 上記 + **dream 由来の「10時まで掃除」** | ❌ **幽霊**（open_loops に無い） |

→ 受け入れの焦点は **「予定を言わない」ではなく「幽霊を言わない · 正しい open_loops は漏らさない」**。

---

## 人間のモデル（まー合意 2026-06-28）

```
6/27 会話: 「明日、角煮しよう」
  uttered_at = 2026-06-27
  → 明日 = 2026-06-28（resolved）

6/28 朝 as_of = 2026-06-28
  → 角煮は「今日」の予定

「明日角煮、いつ言ってたっけ？」がわからない
  → 今日？明日？ と **間違える**（T₀ 喪失）
```

人間が deixis を使い分けられるのは **発言のタイムスタンプ**（＋ timezone での calendar day）があるから。システムも同型。

---

## 三層（保存 · 注入 · 表層）

| 層 | 役割 | 例 |
|----|------|-----|
| **保存** | 原文 + `uttered_at` + **`resolved_date`(s)** | 原文「明日角煮」/ meta `2026-06-28` |
| **注入**（compose / prefetch） | `as_of` と照合 · stale 除外 · 必要なら deixis へ **再 relativize** | 「今日、角煮（6/27 発話では明日）」 |
| **表層発話** | まー向けは **相対日** が自然 | 「今日、角煮作るんやね」— わざわざ「2026年6月28日」とは言わない |

**具体日**は裏方の錨。**会話では昨日/今日/明日**。

---

## 望ましいフロー（例）

```
プロンプト（6/27）: 「明日、角煮を作る」
  ↓ record
保存:
  text_original = "明日、角煮を作る"
  uttered_at    = 2026-06-27T08:00+09:00
  resolved_date = 2026-06-28

注入（6/28 compose, as_of = 2026-06-28）:
  resolved == as_of → inject as 「今日、角煮を作る」
  resolved < as_of  → suppress or [past_context — uttered 6/27]
  resolved > as_of  → 「明日、角煮」

表層: deixis で応答（plan / SOUL）
```

**6/29 に「今日、角煮」と自動再変換する** — 設計上の目標。**現状は未実装**（下 §現状）。

---

## 現状（コード · 2026-06-28）

| 経路 | 書き込み | 読み出し / inject |
|------|----------|-------------------|
| **STM** | ✅ `anchor_relative_dates_in_text` — 「明日」→「2026年6月19日」 | 固定日付のまま · **再 relativize なし** |
| **agent_experience** | ✅ 同上（`store.record_agent_experience`） | 同上 |
| **open loop** | ✅ `resolved_date` + stale close | OL2 パターンが **先行実装** |
| **interpretation_shift** | ❌ 生テキスト（「今日は…」のまま） | `ts` 未使用 · plan が **全文 hold** |
| **remember (LTM)** | 多くは原文 | recall そのまま |
| **dream_digest / morning** | `local_day` fence 文言のみ | 中身の deixis は **再計算なし** |
| **GAPI** | — | 未配線 · 「今日の予定」の authoritative source 候補 |

参照: `social_core.date_resolution` — `anchor_relative_dates_in_text` · `is_resolved_date_stale` · `calendar_anchor_line`

---

## やらない方針

| 案 | 理由 |
|----|------|
| **bare greeting 正規表現の拡張** | 「おはよ」「やあ」… **入口の無限リスト** · 根は **ソース側の stale / 幽霊判定**（TEMP-2/5）で潰す |
| **挨拶で open_loops を隠す** | 正しい今日の予定は **`[open_loops]` から触れてよい** · 禁止対象は幽霊経路のみ |
| **fence 文言だけ** | 「dream_digest は 6/27」ラベルは **中身の「今日」を neutralize しない** |
| **表層に具体日を強制** | 会話として不自然 · 具体日はメタ / ログ / カレンダー用 |

---

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| **TEMP-0** | 本 doc · 三層 · 現状マップ | ✅ |
| **TEMP-1** | `record_interpretation_shift` — `anchor_relative_dates_in_text` + **`resolved_date` 保存**（`ts` = uttered_at） | ✅ migration 008 |
| **TEMP-2** | compose inject — `as_of` と `resolved_date` 照合 · **stale な shift を inject しない** | ✅ `shift_temporal.py` |
| **TEMP-3** | inject 用 **relativize_for_as_of**（具体日 → 今日/明日/…）— 表層向け | ✅ `prepare_shifts_for_inject` |
| **TEMP-4** | `plan.must_include` — shift 全文 hold 廃止 · **幽霊経路**禁止 · open_loops は挨拶可 | ✅ `append_shift_plan_constraints` · **TEMP-4b ✅** `append_bare_greeting_plan_constraints` |
| **TEMP-5** | dream_digest · relevant_memories inject — `reexpress_deixis_for_inject` + stale schedule demote | ✅ |
| **TEMP-6** | GAPI prefetch と役割分担（「今日」= calendar · past = anchored memory） | 💤 GAPI prep-3 後 |
| **TEMP-C1** | **段階分類 Stage 1** — `utterance_kind` ゲート（greeting → 停止） | 🔧 POC · [prottypemarkdown.md](../../prottypemarkdown.md) |
| **TEMP-C2** | **段階分類 Stage 2** — 複合予定 `events[]` 分解 | ✅ POC 合格（入浴角煮 · 2026-06-28） |
| **TEMP-C3** | gateway — Stage1→2 パイプ · events → OL · G1 ガード | ✅ `PRESENCE_GW_S2_STAGED=1` |

**第一縦スライス（保存）**: **TEMP-1 + TEMP-2**（interpretation_shift · 6/28 再発防止）。  
**並行 POC**: **TEMP-C1/C2** — Gemma 4 12B QAT で段階分類が通れば interpret 層が一気に広がる。

---

## TEMP-1 — interpretation_shift 試作（詳細）

### 保存（`interaction_orchestrator_mcp/store.py`）

`record_interpretation_shift` 時:

1. `uttered_at` = 既存 `ts`
2. `new_anchored, resolved = anchor_relative_dates_in_text(new_interpretation, updated_at=ts, tz=policy_tz)`
3. DB に保持（案）:
   - `new_interpretation` — anchored テキスト（OL / STM 同型）
   - `resolved_date` — ISO date または JSON sidecar（複数 slot は後回し）
   - `topic` — そのまま

`old_interpretation` も同様にアンカー可（任意）。

### 注入（compose → compact block / plan）

`recent_interpretation_shifts` を compose に載せる前:

```text
as_of = calendar today (Asia/Tokyo)
for each shift:
  if resolved_date < as_of:
    → 載せない or [past_context — uttered {uttered_day}]
  elif resolved_date == as_of:
    → 「今日」系として載せ可（TEMP-3 で文言を relativize）
  elif resolved_date > as_of:
    → 「明日以降」
```

### plan（TEMP-4 ✅ · 方針更新 2026-06-29）

- bare greeting 正規表現拡張に頼らない — **幽霊はソース側**（TEMP-2/5）で止める
- shift あり + resolved **stale** → compose inject なし（TEMP-2）
- **通常ターン**: `must_include` は topic +「do not regress」だけ — **OLD/NEW 全文 hold しない**
- **「おはよ」**: **`[open_loops]` の今日分は短く触れてよい**（推奨）· dream/shift/stale episode から予定復唱は禁止 — **TEMP-4b ✅** `append_bare_greeting_plan_constraints`
- **「今日の予定は？」**: authoritative = open_loops · shift snippet は open_loops 空時のみ · ghost `must_avoid`（TEMP-4b）
- 詳細は compose の `[interpretation_shifts]` · `[open_loops]` 節を参照

---

## 受け入れ（TEMP-1/2 · 幽霊禁止 · 2026-06-29 更新）

| シナリオ | 期待 |
|----------|------|
| 6/27 に shift「今日入浴介助…」保存 | `resolved_date = 2026-06-27` |
| 6/28 朝「おはよ」 | **入浴介助・角煮を幽霊として言わない**（stale shift / dream 経路）· **open_loops の今日分は短く触れてよい** |
| 6/28 「今日の予定は？」 | stale shift / dream から復唱しない · **open_loops のみ**（GAPI 未接続時） |
| 6/27 夜「明日角煮」→ OL 作成 → 6/28 朝 | open_loops に載っていれば「今日角煮」と触れてよい · shift 全文 hold は不要 |
| 6/29 「おはよ」+ open_loops 3件 | **3件とも漏らさない**（15時ブロック含む）· dream の閉 loop「掃除」は出さない |
| 6/29 「今日の予定？」 | open_loops と一致 · **dream/recall から追記しない** |

---

## 難例 — 複合予定（1 文・多イベント）

**まー合意 2026-06-28** — 当たり前に使うが、機械には難しい。

> 今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。

### 人間が暗黙に持っている構造

```
[今日] 入浴介助 ──(〜15時頃まで? かかりそう)──→ 帰宅 ──(すぐ)──→ 角煮を作る
```

| 層 | 内容 |
|----|------|
| イベント A | **今日** · 入浴介助（仕事） |
| イベント B | **今日** · 角煮を作る |
| A の終了見込み | 〜15時頃まで（**推定・非確定**「かかりそう」） |
| B の開始条件 | A 終了後 · **すぐ**（「帰ってきたら」） |
| B の開始時刻（暗黙） | ≥ 15時前後 |
| メタ | **確定スケジュールではない** — 「**感じだね**」（たたき・合意） |

同一 calendar day でも **同時刻ではない**。因果でつながった **2 スロット**。

### 単一 JSON が失敗する理由（Gemma POC 2026-06-28）

1 段 `future_commitment` + `temporal_phrase: null` + `object: 角煮` だけでは:

- 入浴介助が **落ちる**
- 「今日」が **explicit temporal にならない**
- 15時 / 帰宅後 / すぐ / かかりそう / 感じだね が **全部 flatten される**

→ 6/27–28 の **「今日の予定」すり替え** と同族のデータが stores に残る。

---

## 段階分類（TEMP-C · Gemma 4 12B QAT POC）

**方針**: 1 発 JSON に全部押し込まない。**kind でゲート → 必要なときだけ深掘り**。

```
発話 + uttered_at（+ calendar today 任意）
  │
  ▼ Stage 1 — kind ゲート（軽い JSON）
  │   greeting / other → STOP（temporal 推論禁止 · loop/shift 候補にしない）
  │   future_commitment / past_completion / past_report → Stage 2 へ
  │
  ▼ Stage 2 — events[] 分解（重い JSON · 複合予定向け）
  │   各 event: what, when_phrase, until, after, lag, certainty, depends_on
  │
  ▼ Stage 3 — コード（LLM 不要）
      anchor_relative_dates_in_text(per event, uttered_at)
      resolved_date + stale(as_of)
      commitment_strength: tentative | firm（「感じだね」→ tentative）
```

| Stage | モデル | 出力 |
|-------|--------|------|
| **1** | Gemma 4 12B QAT | `utterance_kind` のみ（+ 最小スロット） |
| **2** | 同上 · Stage1 結果を入力 | kind ごとの専門 schema（例: `events[]` · 将来 `correction_target`） |
| **3** | `date_resolution` + ルーティング | `resolved_date`(s) · store 選択 · inject 可否 |

### Stage の役割（脳機能モデル · 合意 2026-06-28）

[cognitive-layers.md](../architecture/cognitive-layers.md) の **前頭葉 / 表層 / 記憶** に対応させる。

| Stage | 脳のたとえ | やること |
|-------|-----------|----------|
| **1** | 粗い分類 | 相手の発話の **大まかな kind** — 深掘りするか **止めるか** |
| **2** | 専門分解（複数ありうる） | kind に応じた構造化 — 予定なら `events[]`、理解更新なら `correction_target` 等 |
| **3** | 決定的書き込み | **安定した根拠** のみで DB へ — anchor · stale · ルーティング |
| **表層** | 会話 | 構造化済み材料を見て **まー向けの言葉** — Stage 出力を KV に載せない |

**背景**: 以前は (a) 表層 LLM に 1 発で理解+記憶+台詞を押し付ける、(b) regex 1 本で DB 書き込み、が混在していた。Stage 化は **1 発を「分類 → 専門分解 → コード確定」に拆す** こと。速さより **確実性・監査可能性**。

**本番合格例（2026-06-28）**: 「明日掃除 10 時まで、そのあとお昼」→ Stage1 `future_commitment` → Stage2 `events[]`×2（`depends_on`）→ Stage3 anchor `2026-06-29` → open loop×2 · shift なし。

### Stage 2 を増やす判断ルール

新しい Stage 2（例: 理解更新用 `correction_target` · [interpretation-shift-routing.md](./interpretation-shift-routing.md) SHIFT-R2）を足すとき、**毎回** 以下を満たす。

| # | ルール | 理由 |
|---|--------|------|
| **S2-1** | **Stage 1 の kind からだけ起動**（G1: `greeting` / `other` → Stage 2 禁止） | 無関係 utterance への深掘り・GPU hang 防止 |
| **S2-2** | **kind allowlist** — どの Stage 2 プロンプトを呼ぶかコードで固定（G2） | 「なんとなく LLM」に store を任せない |
| **S2-3** | **出力 schema を固定** — 例: `events[]` · `correction_target` + `old`/`new` · `canonical_topic` | Stage 3 がパースできる形だけ許可 |
| **S2-4** | **Stage 3 が使えるフィールドだけ信頼** — anchor 可能な `when_phrase` · ISO 化可能な date · 正規化 topic | LLM 自由文をそのまま DB / plan hold に載せない |
| **S2-5** | **表層 KV に載せない** — `[gateway_internal]` · SOUL なし · resume なし | 会話 KV を前頭葉の JSON で汚さない |
| **S2-6** | **timeout + max_tokens + 件数上限**（G3 · G4） | 複合 JSON の暴走をコードで止める |
| **S2-7** | **store ルーティングは Stage 3** — Stage 2 は「意味構造」まで。open loop / shift / boundary / remember の選択はコード | [interpretation-shift-routing.md](./interpretation-shift-routing.md) のルーティング表と同型 |

**増やしてよい条件（いずれも）**:

- Stage 1 だけでは **destination が決まらない**（予定 vs 事実訂正 vs dismiss 等）
- 1 発 JSON / regex では **構造が落ちる**（複合予定 · 因果 · old→new）
- Stage 3 用の **受け入れテスト** を 3 件以上書ける

**増やさない方がよい**:

- Stage 1 kind + コード数行で足りる
- 出力が **自由文だけ** で Stage 3 が検証できない
- 表層の `must_include` に Stage 2 本文を hold する設計（TEMP-4 で禁止方向）

| Stage 2（例） | Stage 1 kind | 出力 | Stage 3 出口 |
|---------------|--------------|------|--------------|
| **予定分解**（TEMP-C2 · ✅） | `future_commitment` 等 | `events[]` | open loop · anchor |
| **理解更新**（SHIFT-R2 · ✅） | `correction` | `correction_target` · canonical topic | shift · boundary · experience |
| （将来） | `past_report` 専用 | … | experience · loop close |

**POC 合格（C2）**: 上記難例で `events` が **2 件**（入浴介助 / 角煮）· A に `until: 15時位` + `certainty: estimate` · B に `after: 帰宅` + `lag: すぐ` · `commitment_strength: tentative`。  
→ **2026-06-28 Gemma 4 12B QAT で確認済み**（[prottypemarkdown.md](../../prottypemarkdown.md) POC ログ）。

**プロンプト**: リポジトリ直下 [prottypemarkdown.md](../../prottypemarkdown.md) — LM Studio 手試し用。

### Stage 2 期待 JSON（案）

```json
{
  "utterance": "...",
  "utterance_kind": "future_commitment",
  "commitment_strength": "tentative",
  "events": [
    {
      "index": 0,
      "what": "入浴介助",
      "when_phrase": "今日",
      "until_phrase": "15時位まで",
      "certainty": "estimate",
      "action_phrase": null
    },
    {
      "index": 1,
      "what": "豚バラ軟骨角煮",
      "when_phrase": "今日",
      "after_phrase": "帰ってきたら",
      "lag_phrase": "すぐ",
      "action_phrase": "作る",
      "depends_on": 0
    }
  ]
}
```

Gateway は **events ごと** に `resolved_date` を取り、open loop は **action_phrase あり** または **`until_phrase` あり**（duration ブロック · 書類15時まで等）の future event（TEMP-C3b · 2026-06-29）。

**Stage 2 呼び出し kind**: `future_commitment` · `past_completion` · `past_report` — 完了報告は `past_*` を同一経路でよい（POC: 「角煮、作った」が `past_report` でも events 分解は問題なし）。

### 本番接続（TEMP-C3 · 2026-06-28）

**有効化**（`~/.config/embodied-claude/presence-ui.local.env`）:

```env
PRESENCE_GW_S2_ENABLED=1
PRESENCE_GW_S2_STAGED=1
# 任意: PRESENCE_TEMP_C_STAGE1_MAX_TOKENS=420
# 任意: PRESENCE_TEMP_C_STAGE2_MAX_TOKENS=768
# 任意: PRESENCE_GW_S2_TIMEOUT=45
```

`restart-presence-ui.ps1` で反映。ingest 後 `temp_c_staged.py` → Stage1 →（greeting/other なら停止）→ Stage2 → events[] → open loop（**action あり future** · **`until_phrase` あり duration** · TEMP-C3b ✅ 2026-06-29）。

### TEMP-C4 — open loop アンカー ✅ 2026-06-29

**きっかけ（2026-06-29）**: `depends_on` イベントだけ when を持ち、後続 event の topic に **日付プレフィックスが付かない** · `detail.resolved_date` が null → stale / inject が弱い。

例: event1=お昼（when=明日）· event2=県に提出する書類（when=null, depends_on=0）→ topic `県に提出する書類 お昼… 作るよ` · `resolved_date` なし。

| ID | 内容 | 触る場所 | 状態 |
|----|------|----------|------|
| **TEMP-C4a** | Stage2 後 **`inherit_when_phrases`** — depends_on 多段 + Stage1 `temporal_phrase` fallback | `temp_c_staged.py` | ✅ |
| **TEMP-C4b** | `merge_ol_gate_gateway` — temporal が topic に無ければ前置して anchor | `ol_gate.py` | ✅ |
| **TEMP-C4c** | `apply_ol_gate_decision` — 未 anchor topic を temporal / `event.effective_when` から再 anchor | `relationship_mcp/store.py` | ✅ |
| **TEMP-C4d** | depends_on チェーン when 継承 | `inherit_when_phrases` | ✅ |

**受け入れ**: 複合発話の全 open loop に anchored topic / `resolved_date` · 単日は翌日 stale（default）· multi-day は [OL-STALE](../architecture/open-loops-reminders.md#ol-stale--日跨ぎで閉じない-loop)。

| 出口 | 用途 |
|------|------|
| `greeting` | OL-GATE スキップ · shift schedule 載せない · **Stage 2 呼ばない** |
| `events[]` + anchored | interpretation_shift / open loop / STM |
| `commitment_strength: tentative` | GAPI 書込・確定発話を **ゲート** |

GW-S2 OL-GATE（[gw-silent.md](./gw-silent.md)）の 1 段 JSON を **C1/C2 に分割**するイメージ。

#### 必須ガード（POC 2026-06-28 — 「こんにちは」単体を Stage 2 直渡しでハング）

| ID | ガード |
|----|--------|
| G1 | Stage 1 **`greeting` / `other` → Stage 2 禁止** |
| G2 | Stage 2 kind allowlist のみ |
| G3 | LLM **timeout** + **max_tokens** |
| G4 | `events` 件数上限 · JSON 正規化 |

詳細: [prottypemarkdown.md](../../prottypemarkdown.md) §「実装ガード」。

#### 実装順（2026-06-29 更新）

```
① TEMP-1/2 ✅ — shift anchor + stale inject
② TEMP-C3 ✅ — Stage1→2 · events → OL
③ TEMP-C3b ✅ — until_phrase あり duration も OL（2026-06-29）
④ TEMP-3/4 ✅ — compose relativize · plan hold
⑤ TEMP-C4 ✅ — loop `resolved_date` / when 継承 · merge/store anchor 強化
⑥ OL5-c ✅ — e4b completion_verbs 拡張 → [ol5.md](./ol5.md)
⑦ OL6 ✅ — 確認→「終わったよ」close → [ol5.md](./ol5.md)
⑧ OL-STALE ✅ — stale_policy · 日跨ぎ exempt → [open-loops-reminders.md](../architecture/open-loops-reminders.md#ol-stale--日跨ぎで閉じない-loop)
⑨ TEMP-5 ✅ — dream_digest / memories inject re-anchor · stale schedule demote
⑩ SHIFT-R3 ✅ — shift.domain + inject filter → [interpretation-shift-routing.md](./interpretation-shift-routing.md)
```

#### ma-home 運用 — 何が再起動されるか

| プロセス | 役割 | `restart-presence-ui.ps1` |
|----------|------|---------------------------|
| **presence-ui :8090** | compose / plan / `record_interpretation_shift` を **ライブラリ直結** | ✅ 再起動 + `sync-presence-deps` |
| **sociality MCP**（Claude Code `.mcp.json`） | `mcp__sociality__*` ツール用サブプロセス | ❌ **再起動しない** |
| **Claude Code :8080** | brain（native chat 時は任意） | ❌ |

ma-home の Room 会話経路は **presence-ui が orchestrator を in-process で呼ぶ**。TEMP-1/2 の compose フィルタは **presence-ui 再起動で有効**（ログ上 `interaction-orchestrator-mcp` / `social-core` rebuild 済みなら OK）。

**`resolved_date` が null のまま** — 想定どおり:

- migration 008 は **列追加のみ** · **既存行はバックフィルしない**
- TEMP-1 は **新規 `record_interpretation_shift` 書き込み時** にだけ populate
- TEMP-2 は null 行でも `new_interpretation` の「今日」+ `ts`、または anchored 具体日から stale 判定（フォールバック）

**手動 TEMP-1 確認**（`sociality-mcp` ルート · PowerShell）:

```powershell
cd C:\Users\ma\src\embodied-claude\sociality-mcp
uv sync --reinstall-package interaction-orchestrator-mcp --reinstall-package social-core

uv run python -c @"
from interaction_orchestrator_mcp.schemas import RecordInterpretationShiftInput
from interaction_orchestrator_mcp.store import InteractionOrchestratorStore

store = InteractionOrchestratorStore()
stored = store.record_interpretation_shift(
    RecordInterpretationShiftInput(
        person_id='ma',
        topic='schedule anchor test',
        old_interpretation='Assumed default',
        new_interpretation='今日は入浴介助で15時位まで',
        trigger='manual TEMP-1 test',
        confidence=0.9,
    )
)
row = store.recent_interpretation_shifts(person_id='ma', limit=1)[0]
print('shift_id:', stored.experience_id)
print('resolved_date:', row.resolved_date)
print('new_interpretation:', row.new_interpretation)
store.close()
"@
```

`sync-presence-deps` は **presence-ui** 用。上記は **sociality-mcp/.venv** 直叩きなので `--reinstall-package` が別途必要。

期待: `resolved_date` = 今日の ISO 日 · `new_interpretation` に `2026年6月28日` 等。

---

## 既存 shift（入浴介助 / 角煮など）の扱い

6/28 以前の `interpretation_shifts` は **`resolved_date` null · 「今日」生テキスト** のことが多い。

### そのままでよいか？

**compose 再発防止（TEMP-2）だけなら、多くはそのままでよい。**

| 保存内容 | TEMP-2 |
|----------|--------|
| `今日は入浴介助…` + `ts` = 6/27 | `ts` + 「今日」→ 6/27 → **6/28 以降 stale → inject しない** |
| 既に `2026年6月27日…` | 具体日パース → 同上 |
| **日付語なし**（policy 訂正だけ等） | stale 対象外 · inject されうる（意図どおり） |

→ **削除必須ではない**。朝「おはよ」で **stale shift 由来の角煮が出なければ OK**（open_loops に載る正しい角煮は触れてよい）。

### おすすめ — バックフィル（1回）

DB を揃えたい · C3 前に `resolved_date` を信頼したい → **全 null 行を TEMP-1 同型で更新**（dry-run 付き）。

```powershell
cd C:\Users\ma\src\embodied-claude\sociality-mcp
uv sync --reinstall-package interaction-orchestrator-mcp --reinstall-package social-core

# 確認だけ（更新しない）
uv run python -c @"
from social_core import SocialDB
from social_core.date_resolution import anchor_relative_dates_in_text

db = SocialDB()
rows = db.fetchall(
    'SELECT shift_id, ts, topic, new_interpretation, resolved_date '
    'FROM interpretation_shifts WHERE resolved_date IS NULL'
)
for sid, ts, topic, text, _ in rows:
    new_text, resolved = anchor_relative_dates_in_text(text, updated_at=ts)
    print(sid[:16], topic[:24], resolved, (new_text or text)[:50])
db.close()
"@

# 問題なければ apply
uv run python -c @"
from social_core import SocialDB
from social_core.date_resolution import anchor_relative_dates_in_text

db = SocialDB()
rows = db.fetchall(
    'SELECT shift_id, ts, new_interpretation, old_interpretation FROM interpretation_shifts WHERE resolved_date IS NULL'
)
with db.transaction() as conn:
    n = 0
    for sid, ts, new_t, old_t in rows:
        new_anchored, resolved = anchor_relative_dates_in_text(new_t, updated_at=ts)
        old_anchored, _ = anchor_relative_dates_in_text(old_t, updated_at=ts)
        rd = resolved.isoformat() if resolved else None
        conn.execute(
            'UPDATE interpretation_shifts SET new_interpretation=?, old_interpretation=?, resolved_date=? WHERE shift_id=?',
            (new_anchored, old_anchored, rd, sid),
        )
        n += 1
print('backfilled', n, 'rows')
db.close()
"@
```

- **`resolved_date` が取れない行**（日付語なし policy shift）は null のまま · 文言だけ anchor 試行
- **手動テスト行**（`schedule anchor test` 等）が増えたら SQLite で削除してよい

### 削除する場合

```powershell
uv run python -c @"
import sqlite3
from pathlib import Path
c = sqlite3.connect(Path.home()/'.claude/sociality/social.db')
for r in c.execute(\"SELECT shift_id, topic, substr(new_interpretation,1,40) FROM interpretation_shifts ORDER BY ts DESC LIMIT 10\"):
    print(r)
c.close()
"@
```

対象 `shift_id` を確認してから:

```sql
DELETE FROM interpretation_shifts WHERE shift_id = 'shft_...';
```

**方針**: 6/27–28 の入浴介助/角煮は **backfill 推奨**（残しても stale になる）。重複テスト行だけ **delete**。C3 以降は新規 write が TEMP-1 で自動 anchor。

---

## 他トラックとの関係

| トラック | 関係 |
|----------|------|
| **OL2** | `resolved_date` · stale · `needs_date_confirmation` — **テンプレート** |
| **GAPI** | `as_of` の「今日/明日」イベントは calendar · memory の past と混ぜない |
| **MEM-8** | encode 時に deixis を捨てず **uttered_at + resolved** をセットで |
| **morning fence** | fence は補助 · **TEMP が本体** |
| **GW-S2 / OL-GATE** | 1 段 classify → **TEMP-C1/C2 段階分類**へ進化候補 |

---

## コード参照

| モジュール | 内容 |
|------------|------|
| `social_core/date_resolution.py` | anchor · stale · `format_jp_date` |
| `social_core/stm.py` | STM 書き込みアンカー |
| `interaction_orchestrator_mcp/store.py` | experience アンカー · **shift anchor + resolved_date** |
| `presence_ui/gateway/temp_c_staged.py` | TEMP-C3 Stage1→2 · events → OL |
| `presence_ui/gateway/ol_gate.py` | GW-S2 ingest 分岐 · staged フラグ |
| `interaction_orchestrator_mcp/plan.py` | shift `must_include` · bare greeting（部分） |
| `presence_ui/services/memory_context.py` | morning temporal fence |

---

## 関連

- OL 日付: [open-loops-reminders.md](../architecture/open-loops-reminders.md)
- 6/28 事象の inject 分析: 会話ログ `interpretation_shifts` · `dream_digest` fence
