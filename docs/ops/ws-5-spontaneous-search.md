# WS-5 — 自発 Web 検索

**状態**: 🔧 v0 実装済（2026-06-30）· ✅ WS-5b 天気自動（2026-07-15）· ✅ WS-5c minimal（2026-07-15）· v1 e4b は 📋  
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
| **`ws5_spontaneous` v0** | らしい/みたい + 災害・天気・地域・今日 → WS-5 prefetch（`trigger=ws5`） |
| **`ws5b_weather` 5b** | 直球の気温・天気問い → 確認なし prefetch（`trigger=ws5b`）· JMA API 直優先 |
| **`ws5c_offer` 5c** | resolve miss + 狭い事実ギャップ問い → 「調べようか？」→ 同意で WS-2 相当（`trigger=ws5c`） |
| `web_search_direct` | 自律 tick（`browse_curiosity` / LW-7 opt-in） |
| 表層 alone | 共感・一般論（prefetch 非発火時） |

**env**: `PRESENCE_WS5_ENABLED=1`（既定 ON · `0` で v0 無効）· `PRESENCE_WS5B_ENABLED=1`（既定 ON · 5b）· `PRESENCE_WS5C_ENABLED=1`（既定 ON · 5c）· `PRESENCE_WS5C_OFFER_TTL_SEC`（既定 180）· `PRESENCE_WEB_SEARCH_PREFETCH=1` · `PRESENCE_WS5B_COOLDOWN_SEC`（既定 60 · WS-5 と別）

コード: `presence-ui/.../ws5_spontaneous.py`、`ws5b_weather.py`、`weather_api.py`、`ws5c_offer.py`、`search_prefetch.py`、`ws_guard.py`、`native_chat_router.py`

**Resolve / 優先順（prefetch）**: WS-2 明示 → pending 5c 同意/拒否 → WS-5 v0 → WS-5b → WS-5c offer（ASK のみ・SERP なし）

---

## v0 実装（2026-06-30）

- **許可型ゲート** — hearsay + verifiable topic/region/今日（finite regex · verb リスト増殖なし）
- **query** — `extract_spontaneous_search_query`（トピック + 地域 + ローカル日付）
- **配線** — `resolve_web_search_prefetch` → `search_tier`（L0–L2）→ `url_prefetch`
- **表層** — WS-5 用 gateway directive + `user_intent` で prefetch 事実を冒頭に載せる
- **WS-2 優先** — 明示「調べて」は WS-2 のみ（二重走査なし）

### ma-home 確認（北極星 + 梅雨）

1. `restart-presence-ui.ps1`
2. 「今日、関東で地震があったらしいよ」または「沖縄は梅雨が明けたみたい」
3. ログ: `native chat web search prefetch ok` · `trigger=ws5` · `backend=direct_url` or `cache:…`
4. 応答: **prefetch の具体**（震度・明け日など）が冒頭付近にある。捏造 Sources 禁止は WS guard 維持

---

## v1 受け入れ条件（2026-06-30）

### 解釈（e4b）

- `needs_fact_check` — 許可型（「確認して間違いではないか」）
- `fetch_tier` — `instant | direct_url | serp | full`（安い手段から）
- `suggested_query` / 任意 `suggested_urls`

### インフラ（L0–L2 · 実装済 2026-06-30）

| Tier | 内容 | env |
|------|------|-----|
| **L0** | 正規化 query のセッションキャッシュ | `PRESENCE_WEB_SEARCH_CACHE_TTL_SEC`（既定 900） |
| **L1** | DDG Instant（API backends 内・Brave より先） | `PRESENCE_WEB_SEARCH_BACKEND` |
| **L2** | 気象庁など authority URL 直 fetch（梅雨・地震・台風） | — |
| **L2' / 5b** | 気象庁 forecast JSON（松本気温）— confirmation なし自動 | — |
| **L3** | Brave SERP（L1/L2 空のとき） | `BRAVE_SEARCH_API_KEY` |
| **cooldown** | WS-5 自発のみ連打抑制 | `PRESENCE_WS5_COOLDOWN_SEC`（既定 90） |
| **cooldown 5b** | 天気問いのみ（災害 WS-5 と独立） | `PRESENCE_WS5B_COOLDOWN_SEC`（既定 60） |

コード: `search_tier.py` · `web_search.search_api_backends`

### 表層 grounding（prefetch → 会話）

裏で取れても表層が共感だけ、は **失敗**。LLM 任せにしない。

| 層 | 要件 |
|----|------|
| `[web_search_prefetch]` | `trigger=ws5` かつ `status=ok` → **返答の冒頭に prefetch の具体 1 件以上**（directive 明示） |
| `[url_prefetch]` | `status=ok` → excerpt の事実を **共感より先** に述べる（`user_intent` + block directive） |
| 反例 | 沖縄梅雨 — 気象庁 excerpt ありなのに「ええなぁ、夏本番やね」だけ |

検証: ma-home で「沖縄は梅雨が明けたみたい」→ ログ `backend=direct_url` or `url_prefetch` + 応答に **明け日・公式の一言** が入ること。

**既知の隣接問題（2026-06-30）**: prefetch は効いても **compose `[relevant_memories]`** に過去 `episode_close`（例: 蕎麦が LTM に多数）が載り、無関係な昼食話が付く。対策は LTM 禁止ではなく **compose salience 降下** — [compose-topic-retire.md](../tracks/compose-topic-retire.md)（MEM-8g）。

---

## たたき（v1 以降）

- **interpret 判定** — e4b「事実確認して間違いではないか」（許可型 · OL/WS-5 v1 同型）
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
| 「松本の気温、何度？」 | **WS-5b** — 確認なし・気象API/L2 → 数値で答える |
| 「わからへん」級の事実ギャップ（天気以外） | **WS-5c** ✅ — 「調べよか？」→ OK なら WS-2 相当（`trigger=ws5c`） |
| サッカー文脈の曖昧発話 | **自発検索しない** |
| 「調べて」明示 | WS-2 が引き続き担当（WS-5 と二重走査しない） |
| prefetch 空 | 「調べたけどはっきりせえへんかった」と正直に（WS-1 正直化） |

---

## 実装順（合意 2026-06-23 / 2026-06-27）

1. WS-1 + WS-3 ✅  
2. WS-2a → 2b → 2c ✅  
3. GAPI  
4. **WS-5 v0** ✅ — 北極星 **地震シナリオ** で E2E 確認  
5. **WS-5 v1** — e4b `needs_fact_check` + `suggested_query`
6. **WS-5b 軽い問い（天気・気温）** ✅ 実装メモ（2026-07-15）— 直球でも自動 prefetch（確認なし）。気象庁 forecast JSON 直優先、SERP はバックアップ。地域未指定は松本デフォルト。「外暑い？」級まで。助言・因果・雑談は対象外。  
7. **WS-5c 調べるか確認** ✅ minimal（2026-07-15）— resolve miss + 狭い事実問い（手続き/数値等）で offer。同意で WS-2 相当 prefetch。天気は 5b、明示「調べて」は WS-2。full e4b は非対象。

**方針（2026-07-15）**: **Authority／API 直（既存 L0–L2・天気API）で答えが取れるなら確認なし自動**。Brave SERP（L3）や開いた検索は **5c 確認**または WS-2 明示。

**v0（済）**: 災害・天気・「〜らしいよ」+ 日付/地域ヒューリスティクス → prefetch（`ws5_spontaneous.py`）  
**v1 候補**: GW 系 stateless 分類器（OL-GATE / LW interpret と同型 · 許可型フレーミング）  
**5b（済 2026-07-15）**: 伝聞ゲート無しの直球気温・天気 → `ws5b_weather.py` + `weather_api.py`（JMA）。resolve 順: WS-2 → WS-5 v0 → **WS-5b**。  
**5c（済 minimal 2026-07-15）**: 確認付き検索 → `ws5c_offer.py`。優先: WS-2 → pending 同意/拒否 → WS-5 → WS-5b → **5c offer**。

### WS-5b 実装メモ（2026-07-15）

| 項目 | 内容 |
|------|------|
| ゲート | 天気/気温 allowlist + 問い手がかり（finite）。`らしい` 不要。助言・因果は除外 |
| 地域 | 未指定 → **松本**。前提を answer 先頭に1行 |
| 地域コード | office `200000` · class10 `200020`（中部）· AMeDAS `48361`（松本） |
| 成功パス | `https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json` → 数値 answer |
| フォールバック | 既存 `tiered_search`（SERP/L1） |
| trigger | `ws5b`（v0 の `ws5` とは分離） |

### WS-5c 実装メモ（2026-07-15 · minimal）

| 項目 | 内容 |
|------|------|
| ゲート | 問い手がかり（？/何/いつ/どこ/教えて等）∩ 狭い事実トピック（様式·料金·選挙·株価等）。天気/気温は除外（5b） |
| pending | `~/.claude/presence-ui/ws5c_pending.json`（person_id · TTL 既定 180s） |
| 同意 | 短い allowlist（ok/うん/はい/お願い/調べて…）。「大丈夫」は **拒否**（調べなくてええ） |
| 拒否/TTL/無関係 | pending クリア・検索しない。無関係発話は ignore→クリア |
| offer ターン | SERP **しない**。`[ws5c_search_offer]` + 「わからへん、調べようか？」directive |
| 同意後 | WS-2 と同パイプ（`tiered_search`）· `trigger=ws5c` |
| pending +「調べて」 | **先に** `classify_ws5c_reply` → accept なら **stored query** で `trigger=ws5c`（WS-2 抽出に食わせない） |
| topic+「調べて」 | classify ignore → pending クリア → 通常 WS-2 |
| calendar 競合 | `awaiting_confirm` 中は 5c offer 作らない · affirm を 5c に消費しない |
| env | `PRESENCE_WS5C_ENABLED`（既定 ON）· `PRESENCE_WS5C_OFFER_TTL_SEC`（既定 180）· `PRESENCE_WEB_SEARCH_PREFETCH=0` で 5c も無効 |

**非受け入れ（minimal）**: 広い NL 理解 · full e4b `needs_fact_check` · 天気の確認付き検索（5b のまま）· ゲート外の雑談への offer。

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

- **MEM-8g** — compose から話題を降ろす（蕎麦/Episodic 混入）→ [compose-topic-retire.md](../tracks/compose-topic-retire.md)
- **LW-7** — 読書 PAUSE → Web（自律 tick）。共通化 → [alive-lw-read.md](../tracks/alive-lw-read.md)
- **WS-2** — 明示検索・URL prefetch の親仕様
- **GW-SILENT** — 将来の共有 interpret 層 → [gw-silent.md](../tracks/gw-silent.md)

全文: [archive § MEM-5j / WS-5](../archive/backlog-ma-home-full-2026-06-26.md#mem-5j--会話中-websearchlm-studio--cc-websearch2026-06-20)
