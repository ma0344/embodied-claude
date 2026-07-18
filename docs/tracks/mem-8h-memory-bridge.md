# MEM-8h — cue-driven memory bridge（跨 session 連続性）

**合意**: 2026-07-03（まー）  
**親**: [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)  
**関連**: [surface-direct-llm.md](./surface-direct-llm.md) · [compose-topic-retire.md](./compose-topic-retire.md) · stage-2 recall（8b+）

---

## 問題

| 経路 | 役割 | 限界 |
|------|------|------|
| `session_history`（N ターン） | **同 session** の直近連続性 | 新 session_id では空 |
| open loop | 未来約束 | 雑談（梅干し作ろう）は OL にならない |
| compose recall (8b) | 発話ベース semantic | episode が fact を押し出す · cue 弱いと薄い |

**欲しいもの**: まーの発話キーワード（梅干し・収穫）→ LTM/STM を照合 → **日付付き gist** を surface に注入。「さっきも話してた」系の跨 session 連続性。

N ターン transcript は **捨てない**（同 session の直接動機）。bridge は **追加の索引層**（L1→L2）。

---

## 設計方針

```
まー「梅干し、明日収穫する」
  ↓
[Stage 1 分岐] — 記憶 bridge ルートに入れるか（後述）
  ↓
[前頭葉] kw / entity 抽出: 梅干し, 梅, 収穫
  ↓
[索引] kw ごと :18900 recall（+ 将来 8a fact 行）
  ↓
[注入 tier-1 pin]
  [memory_bridge — not for the user]
  - 2026-07-03: まーが梅干しづくりを提案
  - 2026-07-04 OL: 梅の実の収穫（朝から）
```

### Stage 1 でルート分岐（必須ガード）

**「明日の予定」等の定番フレーズは memory bridge に入れない。**

| ルート | 例 | 処理 |
|--------|-----|------|
| `calendar_read` / temporal schedule | 明日の予定 / 明後日何かあった | GAPI read · schedule_facts · **bridge 禁止** |
| `future_commitment` | 明日朝から収穫する | OL-GATE · OL 作成 |
| `recall_utterance` | 煎餅覚えてる？ | 8b stage-2 / divergent |
| **`memory_bridge`** | 梅干し作ろう / 収穫楽しみ | kw → dated gist（**新規**） |
| chitchat | おはよう | skip |

実装タイミング: bridge POC の前でも **分岐表だけ** Stage 1 / intent bucket に書いておく（後からでも可）。

### 弊害と対策

| リスク | 対策 |
|--------|------|
| 誤結合 | entity 辞書 · 共起 · 閾値 |
| episode 洪水 | 8g salience · fact 優先（8a）· **bridge は episodic blob を採用しない** |
| 古い fact | topic_retire · recency |
| 引きすぎ | **cue 語があるときだけ** · 上限 2–3 行 |
| 定番 temporal | Stage 1 で bridge 除外 |
| **弱い bigram cue**（`家に` / `類か`） | **句読点区切りの条のみ**（JP bigram 廃止 2026-07-18） |
| **vision dump 採用** | `VISION_CAPTION` / `DESCRIBE_FAILED` / `Captured image` を bridge 出口で除外 |
| **食事が episode しかない** | **正本は UserAction `meal/confirmed`**（下 §）。言及だけで LTM に「食べた」を書く旧経路は置換対象 |

**向きつき短冊**（会話で過去を使う）: 今の会話の向き ↔ 日付付き短冊。食事カードが第一ノード。巨大 KG ではない → [spontaneity](./spontaneity.md#向きつき短冊ネットワーク合意-2026-07-18) · [mem-8](../architecture/mem-8-encode-retrieve.md#向きつき短冊ネットワーク合意-2026-07-18)。

理想例（合意 2026-07-18）: 「麺類かなぁ」→ bridge / mentionable に  
`まーは直近で7月1日に麺類（蕎麦）を食べた記録がある`  
があり → 「この間は蕎麦食べてたやんなあ」が自然。episode 転写を表に出さない。**食べた断定カードの一次点は UserAction `confirmed` のみ**（下 §）。

**表層に出す食事カード**: 「食べた記録」形のみ。旧 `〜の話をした（食事の話題）` は compose salience / bridge で `do_not_surface`。  
**晩御飯 cue**: カレー等のしっかりめ料理は可。軽食・時間帯ワード（お昼だけ等）は allowlist から外す。

---

## UserAction meal v0（受け入れ正本 · 2026-07-18）

**地位**: 食事カード encode / 晩御飯 retrieve の **唯一の受け入れ正本**（本節以外に仕様を増やさない）。

### 境界

| 系 | 役割 | v0 |
|----|------|----|
| **OpenLoop** | 未完了の約束追跡 · close 仕組みは現状維持 | UA と **同期しない · 二重書き禁止**。OL→UA 自動は **やらない** |
| **UserAction** | 「〇月〇日に〇〇をした」点の行動記録 | kind=`meal` のみ |

### 表・status

- **置き場（仮決定）**: `social.db` 新表 `user_actions`（`open_loops` と同 DB · relationship store）。LTM 自由文は一次点にしない
- status: `intended` | `confirmed`（`cancelled` は任意・v0必須でない）
- **`intended` は compose 表層に出さない**（確認材料のみ）
- **`intended` 寿命（仮決定）**: 作成から **48h** または confirmed/cancelled まで。同一 `(person_id, kind, object)` の intended は新しい方が勝つ
- 自己申告（「カレー食べた」）→ pending なしで直 `confirmed`
- 計画→確認（「今日の夜はカレー」→「もう食べた？」→「うん」）→ `intended` → `confirmed`
- **日付** = 確認発話（または自己申告発話）の DB 上ローカル日（JST）
- object = **allowlist 閉集合**のみ。発明禁止 · **fail-closed**。閉集合 × Stage/e4b で確定可。書き込みは **high confidence のみ**

### 作った / 食べた

- 双方向とも **自動昇格しない**。区別を残す
- 「作った」材料は当面 **OL close** 側から読む（`cook` kind 本格追加は **やらない**）
- 晩御飯話題では両方を材料に出してよい: ate confirmed →「食べたやんな」 / 作ったのみ →「作ってたやんな」（食べた断定なし）
- **retrieve 正本**: **UA confirmed + OL close の両方を読む**（妥協ではない）

### 向き · 旧 encode

- encode = 一次点 · retrieve = 向き。向きグループ = allowlist 辞書（事実捏造しない）
- **旧 `food_topic_encode`（言及＝食べた即書き）は置換**: UA 経路が生きたら episode_close の「食べた記録」LTM 即書きを **止める**（並走しない）。allowlist ヘルパは再利用可
- **S1 誤日付痛み止め（位置づけ）**: UA 本線の前でも、「言及だけで食べた日を書く」を止め／ゲートする別枠スライス。空 recall より誤「今日食べた」の方が痛い

### やらない（v0）

- 食事スロット主分類 · 隣接点自動展開の本格化
- somatic / VISION オフトピック demote（観察中）
- OL→UA 自動 · 作る→食べた含意の自動／半自動昇格 · cook kind 本格追加

### 実装スライス順

1. **S1** — 旧言及＝食べた即書きの停止／ゲート（誤日付痛み止め） ✅
2. **UA-0** — `user_actions` 表 + meal intended/confirmed 書き込み（fail-closed） ✅
3. **UA-1** — 自己申告直 confirmed · 計画→確認 intended→confirmed ✅（決定論 · Stage LLM は後続）
4. **R0** — 晩御飯向き retrieve: UA confirmed + OL close を材料に（表層はつなぎ一言） ✅
5. **R1** — bridge / mentionable を UA カード形に寄せ、旧 LTM「食べた記録」は demote ✅

---

## 実装フェーズ

| # | 内容 | 状態 |
|---|------|------|
| **A** | Surface Direct: `claude_session_resume=False` → compact に session transcript 載せる | ✅ 2026-07-03 |
| **B** | Stage 1 ルート表 + `calendar_read` / temporal 定番 → bridge 禁止 | ✅ 2026-07-03 |
| **C** | bridge POC: kw → recall → `[memory_bridge]` tier-1 pin | ✅ 2026-07-04 |
| **D** | 8a fact 行 + bridge 統合 · plan soft must_include | ✅ 2026-07-04 |

---

## A — Surface Direct transcript in compact（済）

**背景**: CC 時代は `claude_session_resume=True` で compact から全文を落とし JSONL resume に任せていた。Surface Direct には CC KV がない → 注入デバッグに履歴が見えず、LM も `[gateway_turn_context]` だけ読むと cold-start しやすい。

**変更**: `use_surface_direct_path()` のとき `claude_session_resume=False` — compose の `[recent_room_context]` に transcript 全文（trim 付き）。

**併用**:

- `messages[]`: 直近 N ターン（`PRESENCE_SURFACE_HISTORY_TURNS`）— 変更なし
- `compact_prompt_block`: 同じ session の transcript — **Surface Direct で復活**
- 跨 session: 将来 **memory_bridge**（本 doc C）

コード: `presence_ui.gateway.surface_direct.compose_omit_session_transcript_in_compact`

---

## B — Stage 1 ルート分岐（済）

`classify_memory_retrieve_route()` — orchestrator 側で決定論的分岐（LLM 不要）。

| ルート | bridge | stage-2 |
|--------|--------|---------|
| `calendar_read` | ❌ | ❌ |
| `future_commitment` | ❌ | ❌ |
| `recall_utterance` | ❌ | ✅ |
| `memory_bridge` | ✅（C で recall） | ✅ |
| `chitchat` | ❌ | ❌ |
| `compose_default` | ❌ | ✅ |

コード: `interaction_orchestrator_mcp.memory_retrieve_route` · `compose_memory_bridge.py`（gate + recall hook）

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_MEM8H_ROUTE` | `1` | Stage-1 ルート分岐 |
| `PRESENCE_MEM8H_BRIDGE` | `1` | C: kw → `:18900` recall → tier-1 pin |
| `PRESENCE_MEM8H_BRIDGE_KEYWORDS` | `3` | 抽出 kw 上限 |
| `PRESENCE_MEM8H_BRIDGE_N` | `2` | kw あたり recall n |
| `PRESENCE_MEM8H_BRIDGE_MAX_LINES` | `3` | bridge 行上限 |

---

## C — memory bridge POC（済）

**フロー**（compose 第 1 段のあと · stage-2 の後）:

```
memory_bridge ルート && PRESENCE_MEM8H_BRIDGE=1
  → bridge_topic_keywords(user_text)
  → kw ごと GET :18900/recall
  → episodic blob 除外 · compose 既存 fact と dedupe
  → format_bridge_lines（日付 + snippet）
  → compact tier-1 pin [memory_bridge — cross-session cues...]
```

**ガード**（B と共用）:

- `calendar_read` / `future_commitment` / `chitchat` → bridge **走らない**
- 「ねっとわん いつ」→ `compose_default`（bridge ではない · stage-2 は可）
- 「梅干し作ろう」→ `memory_bridge`

**HTTP timestamp**: memory-mcp `GET /recall` が各 item に `timestamp` を返す（日付 gist 用）。

コード:

- orchestrator: `interaction_orchestrator_mcp.memory_bridge`
- gateway: `presence_ui.gateway.compose_memory_bridge.maybe_enrich_memory_bridge`
- compose pin: `_compact_block(..., memory_bridge_lines=...)`

---

---

## D — 8a fact 優先 + plan soft must_include（済）

**8a-lite**（本格 multi-view encode 前）:

- HTTP `/recall` item に `category` · `importance` を返す
- `is_fact_like_row` + `bridge_hit_rank` — 短い fact 行を episode snippet より優先
- compact fact 行は `relevant_memories` に `memory_bridge_fact_row` として最大 2 件追加

**plan**:

- `ctx.memory_bridge_lines` があるとき `must_include` に **soft** 連続性 nudge
- 「前にも話してた」系の自然な一言 OK · 日付の棒読みリスト禁止
- `stay_silent` / `defer` では載せない

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_MEM8H_BRIDGE_FACT_REFS` | `2` | bridge fact を relevant_memories へ昇格する上限 |

コード: `recall_query.is_fact_like_row` · `memory_bridge.bridge_fact_refs` · `plan.append_memory_bridge_plan_constraints`

1. 新 session で「梅干し」→ 過去の梅干し fact / episode gist が日付付きで 1–2 行 surface
2. 「明日の予定」→ bridge 走らず calendar / schedule 経路のみ
3. bridge + OL + relevant_memories が tier cap 内で共存
4. topic_retire 後は bridge からも降ろす

---

## 関連 OL バックログ（別件）

OL-GATE `action_phrase: する` 問題 — object=梅の実 · action=収穫する · completion_verbs を具体化 → [ol5.md](./ol5.md) / GW-S2 activity_frame 改善。
