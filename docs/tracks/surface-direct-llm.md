# Surface Direct LLM — Claude Code を外した表層会話

**合意**: 2026-07-03（まー）  
**地位**: ma-home キオスク native chat の表層実装の正  
**関連**: [cognitive-layers.md](../architecture/cognitive-layers.md)、[gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[heartbeat-loop.md](../architecture/heartbeat-loop.md)

---

## 目的

native chat の **表層返答**から Claude Code 子プロセスを外し、gateway が既に行っている compose / plan / prefetch のあと **LM Studio `/v1/chat/completions` 直叩き**に寄せる。

- 自発性・内面（自律 tick / GW-S1 / direct_actions）は **変更しない**（もともと CC 外）
- 記憶・社会性は **intercept のまま**（CC MCP に頼らない）
- CC harness / ツール宣言 / resume KV のオーバーヘッドを除去

---

## アーキテクチャ（Before → After）

### Before

```
まー → prefetch → intercept (compose/plan) → ClaudeAgent → claude CLI → LM /v1/messages
                                              → finalize_chat_turn
```

### After（本線）

```
まー → prefetch → intercept (compose/plan) → generate_surface_reply → LM /v1/chat/completions
                                              → surface_session JSONL
                                              → finalize_chat_turn
```

### ロールバック

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_SURFACE_DIRECT` | `1` | 表層を直 LM（本線） |
| `PRESENCE_SURFACE_USE_CLAUDE` | `0` | `1` で legacy CC 子プロセスに戻す |

### SOUL / LM Studio

- 表層人格は **`presets/koyori-SOUL.core.md`** → gateway `system` に毎ターン注入（`PRESENCE_SOUL_CORE_IN_APPEND=1`）
- **LM Studio チャットモデルの System Prompt は空** — 二重注入・LM/gateway 矛盾を避ける
- 定番禁止（物理共作・cheerleading 等）は **SOUL.core Deep**。compose `must_avoid` はパス固有のみ（2026-07-18）
- 注入の層分け（表層 / 表層に近い / セッション台本）→ [inject-surface-layers.md](../architecture/inject-surface-layers.md)

---

## プロンプト構成（CC append の移植）

| 層 | 載せ方 |
|----|--------|
| Gateway stable + SOUL + WS guard | `messages[0].role=system` — `build_gateway_stable_append()` |
| compose / plan / must_include | 今ターンの `user` 先頭 — `[gateway_turn_context]`（既存 `apply_gateway_prompt_injection`） |
| prefetch（vision / web / calendar） | 今ターン `user` 末尾（intercept 済み） |
| 過去ターン | **二系統** — (1) `messages[]` 直近 N ターン raw 文 (`PRESENCE_SURFACE_HISTORY_TURNS` 既定 12) (2) compose `[recent_room_context]`（Surface Direct では **全文** · legacy CC は arc のみ） |
| 今ターン user | enriched message（gateway 注入済み） |

履歴は compose が `session_adapter.load_transcript` で読む **social.db**（**session_id スコープ**）。新 session では空 — 跨 session は **[memory_bridge](./mem-8h-memory-bridge.md)**（cue 語 → LTM dated gist）。表層 JSONL は UI 履歴・Persona export 用のミラー。

### Surface Direct と `claude_session_resume`

| 経路 | `claude_session_resume` | compact の session |
|------|-------------------------|-------------------|
| **Surface Direct（本線）** | `False` | 全文 `[recent_room_context]` |
| Legacy CC + sessionId | `True` | arc 1 行のみ（JSONL resume） |

コード: `compose_omit_session_transcript_in_compact()` in `surface_direct.py`。

---

## 永続化

| ストア | パス | 用途 |
|--------|------|------|
| social.db | `~/.claude/sociality/social.db` | compose の session_history、ingest |
| surface JSONL | `~/.claude/koyori-surface/sessions/{session_id}.jsonl` | native 履歴 UI、Persona export |

JSONL 1 行:

```json
{"role":"user","timestamp":"...","text":"まーの生文","enriched":"[gateway_turn_context]…"}
{"role":"assistant","timestamp":"...","text":"うちの返答"}
```

---

## 実装フェーズ

| # | 内容 | 状態 |
|---|------|------|
| 1 | `surface_session.py` — JSONL append / list / load | ✅ |
| 2 | `llm.build_surface_chat_messages` + `generate_surface_reply` | ✅ |
| 3 | `native_chat_router` — direct SSE path | ✅ |
| 4 | `native_history` — surface JSONL 優先、CC JSONL は legacy フォールバック | ✅ |
| 5 | `persona_export` — surface JSONL からも読める | ✅ |
| 6 | テスト + env example | ✅ |
| 7 | （任意）LM streaming SSE | 未 — 現状は 1 チャンク返却で UI 互換 |
| 8 | compact に session transcript（Surface Direct · A） | ✅ |
| 9 | MEM-8h memory bridge（跨 session · C） | ✅ |

---

## intercept パイプライン（compose 周辺）

```
compose（第1段 recall 込み）
  → stage-2 recall（条件付き · 8b+）
  → memory bridge（memory_bridge ルート · 8h-C）
  → enrich / plan
```

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_MEM8H_ROUTE` | `1` | Stage-1 記憶ルート分岐 |
| `PRESENCE_MEM8H_BRIDGE` | `1` | cue 語 bridge recall |

---

## 受け入れ条件

1. `PRESENCE_SURFACE_DIRECT=1`（既定）で native `/api/native/chat` が **claude 子プロセスを起動しない**
2. gateway intercept（compose / plan / silent / direct_action）は CC 経路と同一
3. 返答後 `finalize_chat_turn` が走り、experience / pulse が記録される
4. セッション履歴が UI（native history API）で読める
5. `PRESENCE_SURFACE_USE_CLAUDE=1` で従来 CC 経路に戻せる

---

## 残課題（本トラック外）

- LM streaming（トークン単位 SSE）
- INJECT-TRIM（STM / room_view / desires 間引き）→ [inject-surface-layers.md](../architecture/inject-surface-layers.md)
- A/B 計測（latency / 関西弁遵守 / must_avoid）

## MEM-8b — 条件付き第 2 段 recall（2026-07-03）

Surface Direct では LM の `mcp__memory__recall` ツールループを **復活させない**。代わりに intercept で compose 第 1 段のあと、条件を満たすときだけ gateway が `:18900` へ追加 recall し、`relevant_memories` をマージしてから plan する。

| トリガ | 例 |
|--------|-----|
| `recall_utterance` | 「煎餅覚えてる？」 |
| `temporal_thin` / `temporal_empty` | 「ねっとわん いつ」「明日予定あったっけ？」で mentionable=0 |
| `thin_mentionable` | ヒットはあるが episodic ばかりで surface 0 件 |
| `history_question` | 「前に話した〜」で第 1 段空 |

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_COMPOSE_RECALL_STAGE2` | `1` | 第 2 段 recall |
| `PRESENCE_COMPOSE_RECALL_STAGE2_DIVERGENT` | `1` | 想起系で `recall/divergent` も試す |
| `PRESENCE_COMPOSE_RECALL_STAGE2_N` | `6` | 追加 recall の n |

実装: `presence_ui/gateway/compose_recall_stage2.py` · `interaction_orchestrator_mcp/stage2_recall.py`
