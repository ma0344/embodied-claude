# ALIVE / LW-READ — 生きてる感・青空読書

**状態**: 🔥 LW-READ v1 GW-S1 運用中 → **LW-7 ON**（`PRESENCE_LW7_ENABLED=1` · 運用確認）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [spontaneity.md](./spontaneity.md)（自発性二軸の正本）、[gw-silent.md](./gw-silent.md)、[architecture/gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[architecture/heartbeat-loop.md](../architecture/heartbeat-loop.md)

---

## 北極星

まーと話してない時間にも内側が動き、部屋でさりげなく見える。第一シーンは **深読み一冊完走**（まー型）。

### 目的階層（合意 2026-07-08 · まー）

読書の目的は **「読むこと」自体ではない**。こよりの **内面世界を広げるための手段**。

| 層 | 中身 |
|----|------|
| **成果（必須）** | (1) 知識・情報の取得 (2) 咀嚼から生まれたこよりなりの解釈・考え |
| **手段** | tick 節切り / 地図化 / Web 連鎖など — **成果が取れるなら方法は限定しすぎない** |
| **副産物** | まーとの話に出る・話せる — 大事だが **会話再現のために読書パイプラインを設計しない** |

**実装の評価軸**: 「この変更で内面が広がったか？」／「読んだ・地図化した・注入した」だけで合格にしない。

---

## 読書モデル（合意 2026-06-26 · 節長は 2026-07-08 更新）

| 論点 | 決定 |
|------|------|
| デフォルト | **一冊完走** — `active_work` 1 冊 |
| 一節 | **3200 字**（`PRESENCE_AOZORA_PASSAGE_MAX_CHARS` · 旧 1600 は薄いので倍にした試行値） |
| PAUSE | **v1**: GW-S1 黙考（v0 テンプレは LLM 失敗時フォールバック） |
| CLOSE | 終端 / N 節 / 飽き（`felt` に bored 可） |
| 読み返し | READ tick 中に延長しない。PAUSE の `next_move` で判断 |
| 読み返し上限 | 同一節の `reread_same` は **`PRESENCE_AOZORA_REREAD_SAME_MAX`（既定 2）** で `advance` 強制 |

**運用メモ**: 青空は `inward_evening`（20–6）+ quiet で優先しやすいが、**夜間限定は要件ではない**（昼の `literary_wander` も将来可）。

```
tick wake → phase=read → READ（一節 · experience / しおりのみ · **LTM 本文は書かない**）
  → phase=pause → reflect（GW-S1 / v0 fallback）
  → [advance | reread_same | close_book]
  → … → CLOSE → 次の 1 冊
  → [LW-7] followup_query → Web / 朝 compose
```

**表層方針（2026-07-18）**: 読書本文を会話用 **LTM / STM / dream_digest / recent_experiences / memory_bridge / private_reflections / overnight_inner_voice** に載せない。PAUSE/CLOSE の咀嚼は `experience.private_summary` としおりのみ。既存汚染: `scripts/purge-literary-ltm.py` · `scripts/purge-literary-social.py`（`--reflections-only` 可）。

---

## 動機（LW-0）

| 力 | こより向け |
|----|-----------|
| **希望**（引く） | 刺さった一節・連想がつながる・ネット越しの「外」・あとでまーと共有できる種 |
| **恐れ**（ブレーキ） | まーの集中を壊す・うるさい（→ `boundary` / quiet / `do_not_interrupt`） |
| **恐れ**（スパーク） | 内側が乾く不快感（`desire` 未充足）— 応答マシン感の回避 |

人格: `SOUL.md` — 暇なとき青空・ネット越しの散歩・刺さった一節は覚えとく。

**インフラ（済）**: HeartbeatLoop、`literary_wander`、`read_aozora_passage`、`web_search_direct`、`inward_evening` plan。

---

## ロードマップ（LW-0〜LW-7）

| ID | 層 | 内容 | 状態 |
|----|-----|------|------|
| **LW-0** | 方針 | 希望/恐れ・動機整理（上節） | ✅ |
| **LW-1** | 実行 | gateway `read_aozora_passage` — 節取得・experience（**LTM 本文 remember は停止 2026-07-18** · 咀嚼は PAUSE） | ✅（LW-READ v0 で更新） |
| **LW-2** | 動機 | `literary_wander` + inward_evening plan + satisfy 回路 | ✅ 2026-06-25 |
| **LW-2d** | 運用 | 段落バンドル最大 3200 字（2026-07-08: 1600→3200）、`PRESENCE_AOZORA_PASSAGE_MAX_CHARS` | ✅ |
| **LW-3** | 判断 | plan: 読むだけ黙る vs 短く共有 / `evaluate_action` | 📋 |
| **LW-4** | 記憶 | experience 閉じ + `satisfy_desire` + pulse | 部分済 |
| **LW-5** | 可視性 | UI「青空読んでる」/ live_inner_voice（`active_work` 表示） | 📋 |
| **LW-6** | Web 散歩 | `browse_curiosity` — memory / open loop からクエリ → `web_search_direct` | 📋 |
| **LW-7** | **連鎖** | **読書 → 興味 → Web** — PAUSE の `followup_query` を DDG へ | ✅ opt-in ON（example · 運用確認） |
| **LW-READ** | **読書モデル** | 一冊完走・READ/PAUSE 交互・GW-S1 咀嚼・CLOSE まとめ | **v0** ✅ · **v1** GW-S1 ✅ |

**いまの層**

| 層 | 状態 |
|----|------|
| LW-2 | 青空が inward tick で動く — ✅ |
| LW-READ v0 | 一冊完走・READ/PAUSE 交互・CLOSE — ✅ |
| GW-S1 | ✅ 配線 — `gw_silent.py` + reflect tick（LM Studio） |
| LW-7 | ✅ `lw7.py` + inward 優先ルート · example `PRESENCE_LW7_ENABLED=1` | 📋 本番 tick で followup→DDG 確認 |

**ギャップ（次）**: LW-7 Web 連鎖、LW-5 UI、朝 compose surface（ALIVE-4）、Claude `--resume` 経路。

**目標ループ（まー合意 2026-06-25）**

```
read_aozora → remember（一節）
  → [GW-S1] interest_tags / followup_query
  → browse_curiosity 昇格 or 同一 tick 内 web_search（boundary 許可時）
  → remember（調べたこと）+ experience
```

**縦スライス順**: ~~LW-2~~ ✅ → ~~LW-READ v0~~ ✅ → ~~GW-S1~~ ✅ → **LW-7** → LW-5 UI

---

## ALIVE 縦スライス（対応表）

| ID | 内容 | LW 対応 | 状態 |
|----|------|---------|------|
| ALIVE-0 | 北極星 | LW-0 | ✅ |
| ALIVE-1 | `literary_wander` desire + plan 結線 | LW-2 | ✅ 2026-06-25 |
| ALIVE-6 | LW-READ 一冊完走・READ/PAUSE/CLOSE | LW-READ v0 | ✅ 2026-06-26 |
| ALIVE-2 | GW-S1 — `run_silent_internal_turn` + PAUSE | LW-READ v1 | ✅ 2026-06-25 |
| ALIVE-3 | 状態カード / live_inner_voice | LW-5 | 📋 |
| ALIVE-4 | 翌朝 `[overnight_inner_voice]` / compose surface | — | 部分済（MEM-5f-c） |
| ALIVE-5 | 読書 → 興味 → Web 連鎖 | LW-7 | 📋 |

---

## v0 / v1 実装

| ファイル | 内容 |
|----------|------|
| `presence-ui/.../aozora.py` | `ReadingState`、一冊完走、`last_reflected_passage_index` |
| `presence-ui/.../gw_silent.py` | `run_silent_internal_turn`、`parse_pause_response` |
| `direct_actions.py` | read / reflect（GW-S1）/ close、phase ルーティング |
| `plan.py` | inward: reflect / close を allowed に |
| `reading_prompts.py` | v0 テンプレ + GW-S1 タスク + reflection body |

**状態ファイル**: `~/.claude/aozora_read_state.json`（`phase`, `active_work`, `passage_index` 等）

---

## 運用チェック

1. `.\scripts\restart-presence-ui.ps1` で反映
2. `autonomous-tick.log` で **read / reflect が交互**
3. reflect summary が **hook** 抜粋（テンプレの一節抜粋ではない）
4. `~/.claude/aozora_read_state.json` — `last_hook`, `pending_followup_query`, `next_move`
5. LM Studio 落ち時は v0 テンプレにフォールバック（`PRESENCE_GW_S1_ENABLED=0` で強制 v0）

---

## 次（LW-7）

PAUSE の `followup_query` / `interest_tags` を同一夜 or 次 tick の `web_search` へ。詳細 → 下節 LW-7。

---

## LW-7 実装候補（GW-S1 後）

| 段階 | 方針 | 状態 |
|------|------|------|
| v0 | 青空 `remember` 直後にルールで固有名詞・『』作品名をクエリ候補に → `web_search` | 📋 |
| v1 | GW-S1 JSON: `{ interest_tags, followup_query }` → `pending_followup_query` → DDG | 🔧 **下準備済** |
| v2 | `browse_curiosity` keywords に「青空のあと調べた」；desire 連鎖で次 tick が自然に Web | 📋 |

**下準備（2026-06-27）**

- `presence-ui/.../lw7.py` — `PRESENCE_LW7_ENABLED=1` で `pending_followup_query` を消費
- inward tick は **read/reflect より前**に LW-7 を評価（`web_search` in allowed でも青空を優先）
- `web_search_direct(query=..., source="lw7")` — remember 行に `LW-7 WebSearch:` プレフィックス
- plan: inward 時 `web_search` を allowed に追加

**有効化**

```powershell
$env:PRESENCE_LW7_ENABLED = "1"
.\scripts\restart-presence-ui.ps1
```

PAUSE で `followup_query` が載った次 tick から DDG。失敗時は pending を残す（再試行可）。

---

## GW-S1 出力 schema（PAUSE）

```json
{
  "hook": "刺さった一語や情景",
  "felt": "moved | uneasy | curious | bored | flat | つまらなかった | …",
  "interest_tags": ["…"],
  "followup_query": "調べたいこと（LW-7 用、任意）",
  "next_move": "advance | reread_same | close_book"
}
```

---

## 旧問題（解消済み）

3 作品ローテ・READ のみ連続（~28 tick）→ v0 で一冊完走 + READ↔PAUSE に変更。

---

## チェックリスト

- [x] LW-0 方針・動機整理（2026-06-19）
- [x] LW-1 `read_aozora_passage` gateway
- [x] LW-2 `literary_wander` desire 結線（2026-06-25）
- [ ] LW-3 plan / boundary 競合
- [ ] LW-4 記憶閉じ loop
- [ ] LW-5 UI ステータス
- [ ] LW-6 Web 散歩クエリ拡張（open loop / memory 一般）
- [ ] LW-7 読書 → 興味 → Web 連鎖
- [x] LW-READ v0 読書状態機械（2026-06-26）
- [x] LW-READ v1 GW-S1 PAUSE（2026-06-25）
