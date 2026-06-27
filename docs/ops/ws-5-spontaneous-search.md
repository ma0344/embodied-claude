# WS-5 — 自発 Web 検索

**状態**: 📋 計画済（WS-1〜2c 済の後）  
**合意**: 2026-06-23（たたき）· 2026-06-27（北極星シナリオ — 地震例）  
**親仕様**: [ws-2-conversation-web-search.md](./ws-2-conversation-web-search.md)  
**関連**: [cognitive-layers.md](../architecture/cognitive-layers.md)、[alive-lw-read.md](../tracks/alive-lw-read.md)（LW-7）、[gw-silent.md](../tracks/gw-silent.md)

---

## 北極星シナリオ — 会話中の「興味・疑問」（2026-06-27）

**背景**: 「興味」「疑問」は青空読書（LW-7）だけの問題ではない。会話でまーが外部事実を持ち込んだとき、こよりが **共感で止まらず、確認してから話す** — それが ma-home で欲しい「生きてる」会話の一形。

### 実例（まー合意）

| | 台詞 |
|---|------|
| **まー** | 「今日、関東で地震があったらしいよ」 |
| **いま** | 「そうなん？。怖いなぁ。」 |
| **期待** | 「そうなん？ちょっと調べてみるわ…。」→ **Web search** → 「ほんまや。〇〇で震度6弱やってんなぁ…。」 |

まーは **「調べて」とは言っていない**。報告＋不確かさがあり、こより側に **認知的ギャップ**（本当か・どこ・規模）はあるが、現状の表層は **感情共鳴**（怖いなぁ）に寄りやすい。

### WS-5 が担うこと

| 層 | いま | WS-5 後 |
|----|------|---------|
| **interpret** | 明示「調べて」のみ（WS-2 キュー） | **事実確認の価値**を ingest / plan 前に判定 |
| **身体** | — | `search_prefetch`（WS-2 と同 DDG/Brave） |
| **表層** | 訓練データ＋共感 | `[web_search_prefetch]` 根拠付きで述べる |

**WS-2 との境界**

| | WS-2 | WS-5 |
|---|------|------|
| きっかけ | 「調べて」「検索して」等 **明示** | ニュース報告・天気・災害・数値主張など **暗黙の確認欲** |
| 実装フック | `looks_like_web_search_request` | interpret / plan / 前頭葉 LLM（未） |
| prefetch タイミング | 表返答 **前**（同型） | 表返答 **前**（同型） |

**LW-7 との共通**

どちらも Heartbeat の **interpret → act（Web）→ remember** の「好奇心」枝。差は入力だけ。

| 入力 | 経路 |
|------|------|
| まーの会話発話 | **WS-5**（native chat prefetch） |
| 青空 PAUSE の `followup_query` | **LW-7**（自律 tick、`PRESENCE_LW7_ENABLED`） |

将来は **「事実ギャップがあるか + suggested_query」** を共有スキーマ（前頭葉）に寄せ、WS-5 / LW-7 は出口だけ分ける。

### 期待フロー（gateway）

```
まー発話（地震報告）
  → interpret: utterance_kind ≈ news_report | factual_report
       should_prefetch=true
       suggested_query="関東 地震 {local_date}"
  → search_prefetch（WS-2 既存パイプ）
  → enriched message に [web_search_prefetch]
  → 表層 LM（SOUL + resume）
  → 「調べてみるわ…」+ prefetch 根拠の具体（震度・場所）
  → remember（任意）
```

表層の「ちょっと調べてみるわ」は **台詞**；実際の検索は **表返答前** に gateway が済ませる（WS-2 と同じ — 1 ターンで完結、キオスク音声向き）。

### やってはいけない（同シナリオの反例）

- prefetch なしで震度・場所を **捏造**
- 「怖いなぁ」だけで **事実確認をスキップ**（WS-5 非発火時の現状に近い）
- 毎雑談で検索（「サッカーおもしろかった」→ 検索しない）

---

## 目的

「調べて」等の明示が **なくても**、会話文脈 + interpret / plan / initiative で gateway が検索・prefetch。境界・頻度制御付き。

**北極星**: 上記 **地震シナリオ** — 共感と curiosity を両立し、根拠付きで話す。

---

## 現状

| 経路 | きっかけ |
|------|----------|
| `looks_like_web_search_request` | 「調べて」等のみ → WS-2 prefetch |
| `web_search_direct` | 自律 tick（`browse_curiosity` / LW-7 opt-in） |
| 表層 alone | 共感・一般論（地震例の **いま** 列） |

コード: `presence-ui/.../ws_guard.py`（`_WEB_SEARCH_CUE`）、`search_prefetch.py`、`native_chat_router.py`

---

## たたき（未実装）

- **interpret 判定** — `compose` / plan 前の「今調べる価値あり」（ルール v0 → 前頭葉 LLM v1）
- **query 生成** — 発話 + 日付 + 地域から `suggested_query`（地震例: `関東 地震 2026-06-27`）
- 既存 **`search_prefetch` + `url_prefetch`** 再利用（WS-2b Brave 含む）
- **`evaluate_action` / quiet hours** で抑制（深夜の過剰検索を防ぐ）
- 会話 + `open_loops` から query 候補（行政・様式系は WS-2 松本例と同型）

### interpret 出力イメージ（案）

```json
{
  "utterance_kind": "news_report",
  "needs_fact_check": true,
  "suggested_query": "関東 地震 2026年6月27日",
  "prefetch_reason": "third_party_report_with_verifiable_facts"
}
```

`needs_fact_check=false` → prefetch しない（サッカー雑談・ phatic）。

---

## 受け入れ

| シナリオ | 期待 |
|----------|------|
| **北極星 — 地震報告** | prefetch 実行 → 応答に **根拠ある具体**（場所・震度等）。捏造 Sources 禁止 |
| サッカー文脈の曖昧発話 | **自発検索しない** |
| 「調べて」明示 | WS-2 が引き続き担当（WS-5 と二重走査しない） |
| prefetch 空 | 「調べたけどはっきりせえへんかった」と正直に（WS-1 正直化） |

---

## 実装順（合意 2026-06-23 / 2026-06-27）

1. WS-1 + WS-3 ✅  
2. WS-2a → 2b → 2c ✅  
3. GAPI  
4. **WS-5** — 北極星は **地震シナリオ** で E2E 確認

**v0 候補**: 災害・天気・「〜らしいよ」「〜あったみたい」+ 日付/地域ヒューリスティクス → prefetch（LLM なし）  
**v1 候補**: GW 系 stateless 分類器（OL-GATE / LW interpret と同型）

---

## 認知層

| 層 | WS-5 |
|----|------|
| **解釈・選択** | 「今調べるか」判定（plan / ルール / 前頭葉） |
| **感覚・身体** | DDG/Brave + fetch |
| **前頭葉（任意）** | query 整形・`utterance_kind` 単発 LLM |
| **表層** | prefetch 根拠のみ述べる；共感は根拠の **後** でも **前** でも可 |

→ [cognitive-layers.md § 実装前の 3 問](../architecture/cognitive-layers.md)

---

## 関連トラック

- **LW-7** — 読書 PAUSE → Web（自律 tick）。共通化 → [alive-lw-read.md](../tracks/alive-lw-read.md)
- **WS-2** — 明示検索・URL prefetch の親仕様
- **GW-SILENT** — 将来の共有 interpret 層 → [gw-silent.md](../tracks/gw-silent.md)

全文: [archive § MEM-5j / WS-5](../archive/backlog-ma-home-full-2026-06-26.md#mem-5j--会話中-websearchlm-studio--cc-websearch2026-06-20)
