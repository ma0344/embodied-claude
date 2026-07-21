# Brief S0 — span ラベル規約（意味分解）

**状態**: 📋 規約ロック（2026-07-20）· 金例 G1–G16 · dry-run 注入 `[brief_s0]`（実行なし）· reasoning 既定 ON  
**下流投影方針**: 📋 **D1–D6 ロック**（2026-07-21 · 実装は未 · 下記 § 投影以降 D1–D6）

S0 = Brief の **手前段（意味分解）**。下流の `jobs` / `need_web` / `ua_*` はここ（ラベル）には付けない。

**親**: [intent-bucket-flow.md 原則 D](../architecture/intent-bucket-flow.md)  
**関係**: TEMP-C Stage1 `utterance_kind` は **将来の投影**。Brief+S1 を1分類器にしない。  
**評価プロンプト**: [brief-s0-system-prompt.md](./brief-s0-system-prompt.md)  
**ランタイム**: `PRESENCE_BRIEF_S0`（既定 ON）で受信時 e4b 空撃ち → `gateway_turn_context` に `[brief_s0]`。`PRESENCE_BRIEF_S0_REASONING` で reasoning。実行・S1 置換なし。

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

**分割**: ask が違うとき切る。同じ ask でも **話題・地域・予定の手がかりが違えば分割可**（**D2** · 2026-07-21）。同じ話題の連続は原則 merge（G11）。**hint 差だけの** `report`×2 はしない（G14）。長い自己開示の導入メタ vs 本論は G15。材料列挙・書名導入が相談・依頼の前置きなら単独 `other`/`report` にしない。

---

## ask 閉集合

| ask | 定義 | 入れる | 入れない |
|-----|------|--------|----------|
| `greeting` | 挨拶・開会話 | おはよう | 挨拶＋本題は分割 |
| `report` | 事実・体験・決定・同意の申告 | 食べた、今夜〜する、いいね全部のせ | 行為依頼→`request`、助言求め→`consult` |
| `consult` | 意見・アイデア・事実確認の相談 | どう思う、アイデアある、〜でしょ？、気温はどれくらい | 実行して→`request` |
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

### G9 — 失敗報告（感嘆は独立 other にしない）
`しまった。つまみを買ってくるの忘れてた。` → `[{ask:report, hint:household}]`（1 span）

### G10 — 材料前置き＋consult
`豆腐、もやし、…なんかいいアイデアある？` → `[{ask:consult, hint:household}]`（1 span）

### G11 — 天気雑談（同 ask merge）
`ええ天気やね。外、めちゃくちゃ暑そう。` → `[{ask:report, hint:life}]`（1 span）

### G12 — 迷いの相談
`明日の朝ごはん何にしよう？` → `[{ask:consult, hint:household}]`

### G13 — 事実問い合わせ（search は下流）
`ちなみに、いま、外の気温はどれくらい？` → `[{ask:consult, hint:life}]`

### G14 — 確認＋決断（同 ask 連続は merge）
`今、松本の気温、結構上がっているでしょ？もう外に出る気になれん（笑）これは家にあるもんでなんとかするしかないな`  
→ **推奨**: `consult`（でしょ？）+ `report`（家でなんとか）。代替: 1×`report` に merge。  
→ **禁止**: hint 差だけの `report`+`report`（G15 の導入/本論とは別）

### G15 — 長い自己開示（導入メタ vs 本論）
```
そういえば、僕の生活にかかわることって、あんまり話してなかったね。
僕は COMMON SENSE MATSUMOTO合同会社 っていう会社で 業務執行役員 をしている。
その会社は グループホームコモンセンス松本 っていう名前で事業指定を受けて「ここっち」っていう名前のグループホームを運営しているんだ。
```
→ **推奨**: `report`(導入メタ) + `report`(会社・ここっちの事実) / hint=life  
→ **代替**: 1×`report` に merge も可  
→ **禁止**: 文ごとに 3 分割以上

※ 談話の切れ目（導入/本論）と ask の切れ目は別。ask が同じでも導入メタは 2 span まで許容。

### G16 — 長文・本の議論（タイトルは全体に掛かる）
```
あの『ADHDの僕がグループホームを作ったら、モヤモヤに包まれた』なんだけど、
第一章の「障害に甘えてしまう」のところが気になってて、うちの現場でも似た空気ある気がするんよ。
そのあたり、どう読むのが自然やと思う？この間の第一章の続きとして、そこから一緒に読める？
```
→ `report`(タイトル〜似た空気) + `consult`(どう読む) + `request`(一緒に読める？)  
→ **禁止**: タイトル導入だけを `other`（または単独 span）にする  
→ タイトル句は全体の話題スコープ。後ろの report/consult に内包する

---

## スモーク表（LM Studio / e4b）

合否観点: (1) ask が閉集合 (2) 過剰分割なし (3) にする／にしといて対比 (4) hint の粗さ

### 必須

| ID | 発話（要旨） | 期待 |
|----|--------------|------|
| G1 | カレー食べた | report / household |
| G2 | 今夜カレーにする | report / household |
| G7 | 今夜カレーにしといて | request / household |
| G3 | いいね全部のせ | report |
| G4 | 冷蔵庫…アイデア？＋お願い | consult + request |
| G5 | おはよう。昨夜眠れず。会議憂鬱 | greeting / report / **consult** |
| G6 | 違う、明日じゃなくて明後日 | correction |
| G8 | あーね | other |

### 追加

| ID | 発話（要旨） | 期待 |
|----|--------------|------|
| G9 | しまった。つまみ…忘れてた | report×1（other にしない） |
| G10 | 材料列挙＋アイデアある？ | consult×1 / household |
| G11 | ええ天気やね。外、暑そう | report×1（同 ask merge） |
| G12 | 明日の朝ごはん何にしよう？ | consult / household |
| G13 | いま外の気温はどれくらい？ | consult（jobs/search は下流） |
| G14 | 気温でしょ？＋家でなんとか | consult+report 推奨 · 1×report OK · hint差の report×2 禁止 |
| G15 | ここっち自己開示（長文） | report×1〜2（導入+本論）· 3分割以上 FAIL |
| G16 | モヤモヤ本・読み＋一緒に読む？ | report+consult+request · タイトルを other にしない |

**まだやらなくてよい**: UA propose、Brief↔WS-5b 一致強制のテスト自動化。jobs / web_search の **実装配線**は D1–D6 ロック済み・未実装（下記）。

### LM Studio システムプロンプト（評価用正本）

`docs/tracks/brief-s0-system-prompt.md` を参照（ズレたら先に金例・規約を直し、プロンプトを追従）。

### Reasoning（精度 ↔ レイテンシ）

| 項目 | 決定（2026-07-20） |
|------|-------------------|
| **既定** | **ON**（金例寄り。レイテンシが気になったら OFF） |
| **UI** | 部屋ドロワー **Brief S0** セクション（通常設定。`GET/POST /api/v1/brief-s0/reasoning`） |
| **裏の正本** | `PRESENCE_BRIEF_S0_REASONING`（`presence-ui.local.env` · プロセス即時反映） |
| **表層 thinking** | `PRESENCE_CLAUDE_DISABLE_THINKING` とは **別ノブ**（S0 classifier 専用） |
| **API 配線** | `run_classifier_turn(..., reasoning=bool)` → LM Studio `reasoning_effort`（`medium`/`none`）。未指定時は他 classifier に影響しない |
| **max_tokens** | 既定 **1536（ON）/ 512（OFF）**。reasoning が completion 予算を食うため。`PRESENCE_BRIEF_S0_MAX_TOKENS` で上書き |

**見立て**: 境界の欠検出・過分割は「計算予算不足」型が多い。reasoning OFF のままプロンプト微調整しても代替になりにくい。金例・規約の正しさは別問題。

評価・スモークは **reasoning ON を正**とする（OFF はトレードオフ確認用）。

---

## 投影以降 — D1–D6（合意 2026-07-21）

原則 D の発端: **プロンプト受信時点でルートを確定する**（表層 LLM に How を残さない）。  
例え: **1 span ≈ 1 本の TEMP-C**（投影〜そのルートの実行）。いまは dry-run のみ · **実装未**。

| ID | 決定 | 要旨 |
|----|------|------|
| **D1** | **A** | 1 span = 受信時にルート確定する1単位。実行の物理プロセスは **可能なら並列 N 本**。ターン共有は既定世界・クールダウン・表層合成のみ。ターン単勝 Resolve は却下 |
| **D2** | **B** | 同 `ask` でも話題・地域・予定手がかりが違えば **分割可**。report 内にも追加処理（伝聞検索など）がありうるため |
| **D3** | **C**＋伝聞ゲート | report の事実確認は **許可型**。当面トリガーは **伝聞表現**に限定（際限なく常時検索＝A 化しない）。その span の中身で Resolve（**天気・気温 → JMA / WS-5b**、その他 verifiable → WS-5 系） |
| **D4** | **C**＋既定松本 | 伝聞検証＝**span 内言及地**／天気 consult・地域なし＝**既定松本**。結果を1つの天気話に混ぜない。居住地以外は明示（代名詞含む）が必要。**ねっとわん→松本推論は実装しない**（[MEM-8j](../backlog-ma-home.md) 覚書） |
| **D5** | **A** | Resolve は **ジョブ単位**（並列可）。同一ターンで伝聞 WS-5 と天気 5b が並んでよい |
| **D6** | **A'** | ジョブ結果を **材料ブロック**として渡し、順序・軽重は **表層 12b** に任せる。`consult`＝常に主、は却下（問いでも談話上「ついで」がありうる）。**短い grounding 指示は残す**（材料があるのに共感・応援だけへ逃げるのを防ぐ） |

### 伝聞ゲート（D3 · 当面）

有限 allowlist（ゲートのみ · 人語の意味網羅はしない）。参考:

- 呉 蘭（2012）「日本語の伝聞表現」—「（スル）ソウダ」「ッテ」「ラシイ」の区別  
- [伝聞まとめ（そうだ／らしい／って／と聞きました）](https://nihongo-mistake.com/denbuntoha/)

当面の語彙候補: `らしい` / 伝聞の `そうだ` / 文末寄り `って` / `と聞` / `という話` 等。  
**注意**: 様態の「降りそう」、推量の「らしい」、エコーの「って」と混同しやすい → v0 は狭く始め金例で足す。  
既存 WS-5 v0 の hearsay cue と寄せてよい（実装時に一本化検討）。

### 地域（D4 · v0）

1. 天気 consult: span 内に明示地名がなければ **既定松本**  
2. 伝聞ジョブの言及地（例: 名古屋）は **伝聞専用** — 天気 consult に継承しない  
3. 「直前 span から地名を無条件継承」は禁止（比較伝聞→誤継承）  
4. エンティティ→場所（ねっとわん⇔松本）は **MEM-8j** まで延期

### 表層（D6）

- 材料: ジョブ結果をラベル付きで注入（例: 伝聞検証 / 松本の明日予報）  
- grounding: 材料がある事実には触れる（全部を主題にしなくてよい）  
- 順序・軽重・本題 vs ついで: **12b**（ask ラベルだけでは談話重心は決まらない）

### 仮置き・後回し

| 項目 | 扱い |
|------|------|
| OL-GATE | 従来どおり **ターン側**。S0 `ask` は OL 入力にしない |
| レイテンシ / reasoning 予算 | dry-run 観測後に調整 |
| MEM-8j エンティティ属性マップ | 💤 backlog |
| UA 書込・shadow jobs スキーマ統合 | 投影実装後 |
| 明示 WS-2「調べて」とジョブ並列の詳細 | 実装時に詰める |

### 動機例（2026-07-20 実会話）

複合: 明後日の気温・名古屋40℃らしい・ねっとわん（明後日）・「明日の天気は？」  
全文1本 Resolve だと WS-5（名古屋）が勝ち 5b に届かない。D1–D5 で span/ジョブ並列にすると天気 API と伝聞検証を分けられる。談話上「明日の天気」はついで → D6 で consult 強制主にしない。

---

## 現行影 v0 との関係

`[brief_shadow]`（jobs / ua_candidates）と `[brief_s0]`（spans）は **別スキーマ**。どちらも観測のみ・実行しない。dump では S0 が先（`append_brief_shadow` の後に `append_brief_s0` で先頭へ）。

S0 金例・LM Studio 評価は本 track の ask 規約を正とする。投影 D1–D6 は **方針ロック**であり、影段ではまだ実行しない。

---

## 非目標

- jobs 実行グラフ、`need_web`、UA 書込を S0 **ラベル**に混ぜる  
- Brief+S1 統合分類器  
- 影段でのルート置換（D1–D6 実装までは維持）  
- 人語を regex で切る（分類は e4b / LM Studio · 伝聞ゲートは有限 allowlist のみ）  
- 表層の談話重心を S0 だけで機械決定する（D6）
