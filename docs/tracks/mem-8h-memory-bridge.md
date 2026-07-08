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
| episode 洪水 | 8g salience · fact 優先（8a） |
| 古い fact | topic_retire · recency |
| 引きすぎ | **cue 語があるときだけ** · 上限 2–3 行 |
| 定番 temporal | Stage 1 で bridge 除外 |

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
