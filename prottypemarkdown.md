# TEMP-C — 段階分類プロトタイプ（Gemma 4 12B QAT）

LM Studio 等で **2 段**に分けて試す。Stage 1 が `greeting` なら **Stage 2 を呼ばない**。

設計: [docs/tracks/utterance-anchoring.md](./docs/tracks/utterance-anchoring.md) §「段階分類」

---

## Stage 1 — kind ゲート

**入力**: 発話 1 文のみ  
**出力**: 軽い JSON · `greeting` なら temporal 推論 **禁止**

```
あなたは会話発話の分類器です。与えられた発話 1 文を解析し、**必ず次の順序**で考えてから JSON 1 件だけを出力してください。

**手順**

1. `utterance_kind` を先に 1 つ決める
2. `object_phrase` / `action_phrase` — 文中の語だけ（推測禁止）
3. `temporal_phrase` — 文中の「いつ」だけ（推測禁止）
4. `inferred_temporal_phrase` — 手順3が null かつ kind が許すときだけ

**utterance_kind**

| 値                   | 意味      | 例                 |
| ------------------- | ------- | ----------------- |
| `future_commitment` | これからの予定 | 明日角煮を作る / ごはん食べる  |
| `past_completion`   | やり終えた報告 | 角煮、作った / 散歩行ってきた  |
| `past_report`       | 過去の出来事  | 昨日、ロバがコケた         |
| `greeting`          | 挨拶      | また明日！/ おはよう / またね |
| `other`             | 願望・雑談   | いつも一緒にいたかった       |

**注意**: 「また明日」→ `greeting`。「いつも」は予定の when にしない → `other`。完了形（作った・行ってきた）→ `past_completion`。

**inferred_temporal_phrase**（いつだけ推測可）

* `future_commitment` かつ when なし → 「今日」など可
* `past_completion` かつ when なし → 「いま」「今日」など可
* `other` / `past_report` / `greeting` → **常に null**

**出力 JSON のみ**

```json
{
  "utterance": "...",
  "utterance_kind": "future_commitment | past_completion | past_report | greeting | other",
  "temporal_phrase": null,
  "inferred_temporal_phrase": null,
  "temporal_source": "explicit | inferred | null",
  "object_phrase": null,
  "action_phrase": null,
  "action_terms": [],
  "completion_verbs": [],
  "ineligibility_reason": null
}
```

**較正例**: いつも一緒に→other / 明日角煮→future_commitment / 昨日ロバ→past_report / また明日→greeting / 角煮作った→past_completion / 散歩行ってきた→past_completion / 昼から出かける→future_commitment / ごはん食べる→future_commitment / おはよ→greeting（temporal すべて null）
```

### Stage 1 試験 utterance

| utterance | 期待 kind | 備考 |
|-----------|-----------|------|
| おはよ | greeting | temporal すべて null |
| こにゃにゃちわ | greeting | 同上 |
| 明日角煮を作る | future_commitment | temporal explicit |
| 今日は入浴介助で15時位まで…角煮…感じだね | future_commitment | Stage 2 へ · temporal_phrase は「今日」可 |

---

## Stage 2 — events[] 分解

**入力**: 発話 + Stage 1 の `utterance_kind`（`greeting` / `other` なら **呼ばない**）  
**対象 kind**: `future_commitment` · `past_completion` · `past_report`

```
あなたは会話発話のイベント分解器です。Stage 1 で utterance_kind が決まった発話を、**文中の語だけ**で events[] に分解し JSON 1 件だけを出力してください。

**ルール**

1. 1 文に複数の予定・報告があるときは **events を複数**にする（最大 4）
2. 推測で日付を足さない — when / until / after / lag は **原文に現れる語句**のみ
3. `depends_on` — 後の event が前の event の後だと文から読めるとき、前の index を入れる
4. `certainty` — 「かかりそう」「かも」→ `estimate` · 断定 → `firm` · 不明 → null
5. `commitment_strength` — 全体のトーン。「感じだね」「かな」→ `tentative` · 断定 → `firm`
6. `greeting` / `other` 用の Stage 2 は **出力しない**（呼び出し側がスキップ）

**フィールド**

| フィールド | 意味 |
|-----------|------|
| `what` | 対象・活動（入浴介助 / 豚バラ軟骨角煮 等） |
| `when_phrase` | 今日 / 明日 / 昨日 … 文中の deixis |
| `until_phrase` | 〜15時位まで 等 |
| `after_phrase` | 帰ってきたら 等 |
| `lag_phrase` | すぐ 等 |
| `action_phrase` | 作る / 食べる 等 |
| `depends_on` | 依存する event の index · なければ null |

**出力 JSON のみ**

```json
{
  "utterance": "...",
  "utterance_kind": "future_commitment",
  "commitment_strength": "tentative | firm",
  "events": [
    {
      "index": 0,
      "what": "...",
      "when_phrase": null,
      "until_phrase": null,
      "after_phrase": null,
      "lag_phrase": null,
      "action_phrase": null,
      "certainty": "estimate | firm | null",
      "depends_on": null
    }
  ]
}
```

**較正例（必須合格）**

発話:
「今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。」

期待:
- `commitment_strength`: `tentative`
- `events[0]`: what=入浴介助, when_phrase=今日, until_phrase=15時位まで, certainty=estimate
- `events[1]`: what=豚バラ軟骨角煮, when_phrase=今日, after_phrase=帰ってきたら, lag_phrase=すぐ, action_phrase=作る, depends_on=0
```

### Stage 2 試験 utterance

| utterance | 期待 events 数 | 備考 |
|-----------|----------------|------|
| 明日角煮を作る | 1 | 単純 |
| 入浴介助+角煮（上記全文） | 2 | POC 合格ライン |
| 角煮、作った | 1 | past_completion / past_report どちらも可 · when なし可 |

---

## Stage 3 — コード（LLM 不要 · 将来 gateway）

各 `event.when_phrase` を `uttered_at` + timezone で `resolved_date` にアンカー。  
`is_resolved_date_stale(resolved, as_of)` で inject 可否。  
詳細: `social_core.date_resolution` · [utterance-anchoring.md](./docs/tracks/utterance-anchoring.md)

---

## POC ログ（手書き）

| 日付 | Stage | utterance | 結果 | メモ |
|------|-------|-----------|------|------|
| 2026-06-28 | 1 | おはよ | greeting ✅ | temporal null |
| 2026-06-28 | 1 | こにゃにゃちわ | greeting ✅ | |
| 2026-06-28 | 1 | 入浴介助+角煮 | kind ✅ · flat ❌ | temporal=「帰ってきたらすぐ」· object=角煮のみ · 入浴介助落ち |
| 2026-06-28 | 2 | 入浴介助+角煮 | **POC 合格 ✅** | events×2 · depends_on=0 · tentative · 下 §Stage 2 判定 |
| 2026-06-28 | 2 | 明日角煮を作る | ✅ | events×1 · when=明日 · action=作る |
| 2026-06-28 | 2 | 角煮、作った | ✅ | events×1 · action=作った · kind=past_report（Stage1 なら past_completion 可） |
| 2026-06-28 | 2 | こんにちは+入浴角煮 | ✅ | events×2 · 文頭挨拶は無視 |
| 2026-06-28 | 2 | こんにちは（単体） | ❌ ハング | Stage 2 直渡し · G1 ゲート必須 |

### Stage 2 判定 — 入浴介助+角煮（2026-06-28 · Gemma 4 12B QAT）

| 項目 | 期待 | 実際 | |
|------|------|------|--|
| events 数 | 2 | 2 | ✅ |
| [0] what | 入浴介助 | 入浴介助 | ✅ |
| [0] when | 今日 | 今日 | ✅ |
| [0] until | 15時位まで | 15時位まで | ✅ |
| [0] certainty | estimate | estimate | ✅ |
| [1] what | 豚バラ軟骨角煮 | 豚バラ軟骨角煮 | ✅ |
| [1] after / lag / action | 帰ってきたら / すぐ / 作る | 同左 | ✅ |
| [1] depends_on | 0 | 0 | ✅ |
| commitment_strength | tentative | tentative | ✅ |
| [1] when_phrase | 今日（案） | **null** | ⚠️ 許容 — 「今日」は文頭1回のみ · Stage 3 で [0] から継承可 |
| [1] certainty | null | **`"null"` 文字列** | ⚠️ gateway で JSON null に正規化 |

**結論**: TEMP-C2 の **必須合格ラインをクリア**。12B QAT + 段階分類で複合予定が取れる POC 成立。

**単純文（2026-06-28 追試）**: 「明日角煮を作る」「角煮、作った」も events×1 で安定。複合文専用プロンプトが単純文を壊していない。

| utterance | 要点 | 備考 |
|-----------|------|------|
| 明日角煮を作る | when=明日 · action=作る · firm | ✅ |
| 角煮、作った | action=作った · when=null | kind=`past_report` — Stage 1 較正例は `past_completion`。gateway では **past_* まとめて Stage 2 可**（完了報告として同処理） |
| こんにちは + 入浴角煮（1文） | events×2 · 挨拶無視して分解 | ✅ 文中に予定があれば Stage 2 は機能 |
| こんにちは（単体） | **Stage 2 に直渡し** | ❌ GPU 高負荷 · 応答なし（ループ推定）→ **Stage 1 ゲート必須** |

---

## 実装ガード（TEMP-C3 · 必須）

POC では手動で kind を渡すが、**本番で Stage 2 を無条件呼び出ししない**。

| ガード | 内容 |
|--------|------|
| **G1 kind ゲート** | Stage 1 完了 · `greeting` / `other` → **Stage 2 呼ばない** |
| **G2 allowlist** | Stage 2 は `future_commitment` · `past_completion` · `past_report` のみ |
| **G3 タイムアウト** | LLM コール上限（例 15–30s）· 超過 → フォールバック（flat anchor またはスキップ） |
| **G4 max_tokens** | 出力 JSON 上限（例 512–1024）· 無限生成抑止 |
| **G5 max_events** | パース後 `len(events) <= 4` · 超過は切り捨て or 失敗 |
| **G6 JSON 正規化** | `"null"` 文字列 → JSON null · `depends_on` 継承で `when_phrase` 補完 |

**ネガティブテスト**: 「こんにちは」単体を Stage 2 に渡すとハング — **G1 がないと再現する**。

**複合文**: 「こんにちは。今日は…」は Stage 2 単体でも events 分解 ✅。本番は Stage 1 が `greeting` だけ返す可能性あり → **挨拶+予定** は将来 `utterance_kind` 拡張 or Stage 1 で `future_commitment` 優先ルール要検討（C3 後回し可）。

## LM Studio での試し方

### Stage 1 と Stage 2 を **1 つのシステムプロンプトに連結しない**

両方を system に入れると:

- 毎回 Stage 1 の JSON スキーマに引っ張られる
- greeting テストが重くなる
- 複合文でも **1 object / 1 temporal** の flatten が続く（いまの入浴角煮結果と同型）

**Stage 1 は今のまま単体** — kind ゲート専用。

### 推奨: **別コール**（または同一チャットの **2 ターン目**）

```
[コール A]  system = Stage 1 のみ
            user    = 発話 1 文
            → JSON（kind 判定）

kind が greeting / other → 終了

[コール B]  system = Stage 2 のみ   ← Stage 1 の「後ろに追記」はここ（別 system）
            user    = 下記テンプレ
            → events[] JSON
```

**同一チャットで続ける場合**（system は Stage 1 のまま）:

1. user: 発話 → assistant: Stage 1 JSON
2. user: Stage 2 用ユーザーメッセージ（下記）→ assistant: Stage 2 JSON

system を Stage 1+2 連結に **差し替えない**。2 ターン目は **user に Stage 2 指示を載せる**。

### Stage 2 ユーザーメッセージ（テンプレ）

```
utterance_kind は future_commitment です。次の発話を events[] に分解し、Stage 2 の JSON スキーマだけを出力してください。

発話:
「今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。」
```

`utterance_kind` だけ渡せば足りる。Stage 1 の `object_phrase` / `temporal_phrase` は **Stage 2 に渡さない**（誤った flatten を固定化するため）。

### Stage 1 の入浴角煮結果の読み方

| 項目 | 値 | 判定 |
|------|-----|------|
| `utterance_kind` | future_commitment | ✅ Stage 2 へ進んでよい |
| `temporal_phrase` | 帰ってきたらすぐ | ⚠️ B の after/lag を when に吸い上げ · 「今日」未捕捉 |
| `object_phrase` | 豚バラ軟骨角煮 | ⚠️ 後半だけ · 入浴介助なし |

→ **Stage 1 は「複合文を正しく分解する」責務を持たない**。kind が合っていれば Stage 2 の入力条件は満たしている。
