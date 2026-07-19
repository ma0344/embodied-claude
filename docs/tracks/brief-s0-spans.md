# Brief S0 — span ラベル規約（意味分解）

**状態**: 📋 規約ロック（2026-07-19）· ランタイム未実装（金例・LM Studio 評価用）  
**親**: [intent-bucket-flow.md 原則 D](../architecture/intent-bucket-flow.md)  
**関係**: TEMP-C Stage1 `utterance_kind` は **将来の投影**。Brief+S1 を1分類器にしない。

S0 = Brief の **手前段（意味分解）**。下流の `jobs` / `need_web` / `ua_*` はここには付けない。

---

## 段と優先

| 段 | 意味正本 | 挙動 | 不一致 |
|----|----------|------|--------|
| **影（いま）** | 既存 S1 が実行正本 | S0 は観測・金例評価のみ | ログのみ |
| **投影以降** | **Brief（S0）優先** | S0 → S1 kind へ投影 | マップ不能 = `other` |

- **複合は分割**: 1 span = ask 1つ  
- **曖昧は不要側**: 過検出より欠検出（request / search 種に寄せない）

---

## `spans[]` 最小フィールド

```json
{
  "utterance": "<ターン全文>",
  "spans": [
    {
      "text": "<utterance の連続部分文字列>",
      "ask": "greeting|report|consult|request|correction|other",
      "hint": "calendar|life|household|none"
    }
  ]
}
```

| フィールド | 必須 | 規約 |
|------------|------|------|
| `utterance` | 金例で必須 | ターン全文 |
| `spans` | 必須 | 単一意味でも長さ ≥ 1 |
| `spans[].text` | 必須 | 連続部分文字列・出現順。つなぎは省略可 |
| `spans[].ask` | 必須 | 下表の閉集合のみ |
| `spans[].hint` | 任意 | 省略時 = `none` |

**金例に付けない**: `jobs` / `need_web` / `ua_*` / S1 `kind` / ツール名  

**分割**: ask が違うときだけ切る。同じ ask はまとめる。材料列挙が相談・依頼の前置きなら単独 `report` を必須にしない。

---

## ask 閉集合

| ask | 定義 | 入れる | 入れない |
|-----|------|--------|----------|
| `greeting` | 挨拶・開会話 | おはよう | 挨拶＋本題は分割 |
| `report` | 事実・体験・決定・同意の申告 | 食べた、今夜〜する、いいね全部のせ | 行為依頼→`request`、助言求め→`consult` |
| `consult` | 意見・アイデアの相談 | どう思う、アイデアある | 実行して→`request` |
| `request` | こよりへの行為・記録依頼 | 調べて、入れといて、お願い | 自己決定の宣言のみ→`report` |
| `correction` | 訂正 | 違う、明後日 | 新規報告→`report` |
| `other` | 分類不能 | 短い相づちで確信なし | 無理に5種へ押し込めない |

**境界ロック**

| 発話 | ask |
|------|-----|
| 今夜カレーにする | **`report`** |
| 今夜カレーにしといて | **`request`** |
| いいね全部のせ | **`report`**（search 種にしない） |

### hint（粗い）

`calendar` | `life` | `household` | `none` — 曖昧なら `none`。

---

## 金例（手ラベル）

### G1 — 単一 report
`カレー食べた` → `[{ask:report, hint:household}]`

### G2 — 予定申告 = report
`今夜カレーにする` → `[{ask:report, hint:household}]`

### G3 — 同意 = report
`いいね全部のせ` → `[{ask:report, hint:none}]`

### G4 — consult + request
`冷蔵庫に卵と玉ねぎあるんだけど、何かアイデアある？それで晩ごはんお願い`  
→ consult（前半）+ request（お願い）

### G5 — greeting / report / consult
`おはよう。昨夜眠れず。会議憂鬱`  
→ greeting / report(life) / consult(calendar)

### G6 — correction
`違う、明日じゃなくて明後日` → `[{ask:correction, hint:calendar}]`

### G7 — request（G2 対照）
`今夜カレーにしといて` → `[{ask:request, hint:household}]`

### G8 — other
`あーね`（確信なし）→ `[{ask:other, hint:none}]`

---

## 現行影 v0 との関係

`[brief_shadow]`（jobs / ua_candidates）は **S0 `spans` と同一スキーマではない**。下流観測用。S0 金例・LM Studio 評価は本 track の ask 規約を正とする。

---

## 非目標

- jobs 実行グラフ、`need_web`、UA 書込を S0 ラベルに混ぜる  
- Brief+S1 統合分類器  
- 影段でのルート置換  
- 人語を regex で切る（分類は e4b / LM Studio）
