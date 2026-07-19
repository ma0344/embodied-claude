# MEM — 記憶パイプライン（4 層・昇格・Dreaming）

**関連**: [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md)、[cognitive-layers.md](./cognitive-layers.md)、[heartbeat-loop.md](./heartbeat-loop.md)  
**全文アーカイブ**: [§ MEM](../archive/backlog-ma-home-full-2026-06-26.md#mem--記憶層セッション跨ぎ--dreaming)

---

## 問題

ネイティブ会話は **セッション単位の window** だが、体験・身体・関係は **24h 連続**。「さっき目どうなった？」は層をまたいだ recall が要る。

**方針（2026-06-18）**: OpenClaw 移行はしない。**Dreaming**（短期→長期）を既存 stack に載せる。WM はセッション中にも STM へ。Deep は `SOUL.md` 級。

**セッション**: 廃止しない。セッション = WM の UI 境界。連続性は compose + STM/LTM が担う。

---

## 4 層モデル

| 層 | 保持 | 実装（2026-06） | ギャップ |
|----|------|-----------------|----------|
| **WM** | ターン〜セッション | `session_history`、WorkingMemoryBuffer、JSONL | MEM-2 締めで STM へ |
| **STM** | 〜24h | `agent_experiences`、`body_affliction`、会話断片 | 専用 STM スキーマ混在 |
| **LTM** | 月〜年 | Chroma、`consolidate` | Dreaming 入力未統合 |
| **Deep** | 年〜 | `SOUL.md`、`interpretation_shift`、daybook | 昇格ルール未明示 |

---

## 昇格パイプライン（目標）

```
WM（セッション）
  │  finalize / remember / experience
  ▼
STM（日次）
  │  Dreaming（夜間 pulse）
  ▼
LTM（Chroma）
  │  稀な整理・忘却
  ▼
Deep（SOUL / arc）
```

- **WM→STM**: 会話終了を待たない。エピソード単位要約（MEM-2）。
- **STM→LTM**: 睡眠バッチ — experiences + afflictions + 要約 + somatic digest → `consolidate` + daybook。BIO-8d escalation push 形の `body_affliction` は LTM remember しない（STM dreamed / digest は可）。**desire satisfaction / VISION raw dump も会話 LTM へ書かない**（既定 OFF · purge: `scripts/purge-telemetry-ltm.py`）。
- **LTM→Deep**: 低頻度。`interpretation_shift`、arc → SOUL パッチは **人間承認**（MEM-6）。

### 既存資産

| 資産 | 役割 |
|------|------|
| memory-mcp working memory | WM |
| `social.db` experiences / affliction | STM 候補 |
| `:18900/consolidate` + BIO-4 | Dreaming 核 |
| `recall_divergent` | LTM 広がり |
| `append_daybook` / compose | 注入 |
| `body_state.json` | 身体横断 |

---

## 実装フェーズ（状態）

| ID | 内容 | 状態 |
|----|------|------|
| MEM-0 | 4 層 + 昇格図 | ✅ |
| MEM-1 | STM ストア（`stm_entries`、flush API） | ✅ |
| MEM-2 | WM→STM エピソード締め | ✅ |
| MEM-2b | idle / quiet hours 自動締め | ✅ |
| MEM-3 | Dreaming ジョブ | ✅ |
| MEM-4 | 朝注入（digest + STM） | ✅ |
| MEM-5 | STM→LTM 採点 | **5a–5c 済** |
| MEM-5d | LTM 忘却・重複統合 | 未 |
| MEM-5e | digest / inner_voice 分割 | ✅ |
| MEM-5f | 心の声 2 系統 | **未** |
| MEM-6 | Deep 昇格 | 未 |
| MEM-7 | JSONL ライフサイクル | 未 |
| MEM-8 | encode/retrieve 非対称 | 概念済 → [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md) |

---

## MEM-5e — Dream digest 分割（済）

| チャンネル | 含める | 含めない |
|-----------|--------|----------|
| `[dream_digest]` | episode_close、open_loop_progress、interpretation_shift、body_affliction | 生の `agent_private_reflection` |
| `[overnight_inner_voice]` | 夜間 LLM 合成（2〜4 テーマ） | 15 分 tick の羅列 |

目安: digest 2400〜2800 字、inner_voice 1200〜1800 字。

---

## MEM-5f — 心の声 2 系統（未）

| 系統 | タイミング | 載せ方 |
|------|-----------|--------|
| **ライブ** | その時々 | UI 状態カード（`koyori-voice.js`） |
| **振り返り** | 夜・朝 | `[overnight_inner_voice]` のみ |

**Phase A（優先）**: `compact_prompt_block` 貼り付けやめ、private reflection を UI に surface。  
**Phase B**: Dreaming 末尾で private_reflections → LLM 1 回 thematic summary。

---

## MEM-5k — daybook が薄い（未）

**症状**: `narrative_daybooks.summary` が汎用1行テンプレ。digest / inner_voice には厚い内容があるのに表層に出ない。

**候補**: Dreaming で digest を daybook LLM に渡す / `build_day_summary` を STM ベースへ / `evidence_json` を surface。

**優先**: 中（digest が朝の主経路の間は緊急度低）

---

## その他 MEM-5 派生

| ID | 内容 | 状態 |
|----|------|------|
| MEM-5h | 視覚 experience の compose 圧縮（same scene ×N） | ✅ |
| MEM-5i | Slash `# /observe` がまー発言に見える → export 除外 | 表示 ✅ / 身体は OBS-4 |
| MEM-5j | 会話 WebSearch | → [ws-2](../ops/ws-2-conversation-web-search.md) |

---

## MEM-7 — JSONL ライフサイクル（未）

**現状（C10 済）**: 正本は `~/.claude/projects/.../{session_id}.jsonl`。hide は UI のみ（ファイル残る）。

**方針**: エピソード締め + Dreaming 昇格後、保持ポリシーで archive/delete。キオスク UI からは消さない。

| サブ ID | 内容 |
|---------|------|
| MEM-7a | メタ index（closed_at, stm_id, dreamed_at） |
| MEM-7b | `PRESENCE_JSONL_RETENTION_DAYS` |
| MEM-7c | archive gzip + safe delete |

**依存**: MEM-3 後が安全。

---

## MEM-2 締め（要約）

| 分類 | STM への落とし |
|------|----------------|
| 常時短文 | affliction、境界、remember 直行 |
| エピソード締め | 会話ブロック要約 |
| 入れない | 挨拶、ツール生ログ、LTM 重複 |

トリガー: 新規会話、idle（既定 20 分）、quiet hours 開始。

---

## MEM-5 採点（要約）

`promote_score` = recency + frequency + emotion + interest。閾値 0.55。  
試作: `social_core/stm_scoring.py`、`scripts/score-stm-entries.py`。
