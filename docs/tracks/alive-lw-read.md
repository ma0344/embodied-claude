# ALIVE / LW-READ — 生きてる感・青空読書

**状態**: 🔥 LW-READ v0 運用中 → 📋 v1 GW-S1  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [gw-silent.md](./gw-silent.md)、[architecture/gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[architecture/heartbeat-loop.md](../architecture/heartbeat-loop.md)

---

## 北極星

まーと話してない時間にも内側が動き、部屋でさりげなく見える。第一シーンは **深読み一冊完走**（まー型）。

---

## 読書モデル（合意 2026-06-26）

| 論点 | 決定 |
|------|------|
| デフォルト | **一冊完走** — `active_work` 1 冊 |
| 一節 | **1600 字**（`PRESENCE_AOZORA_PASSAGE_MAX_CHARS`） |
| PAUSE | **v0**: テンプレ内省 / **v1**: GW-S1 黙考 |
| CLOSE | 終端 / N 節 / 飽き（`felt` に bored 可） |
| 読み返し | READ tick 中に延長しない。PAUSE の `next_move` で判断 |

```
tick wake → phase=read → READ（一節・remember）
  → phase=pause → reflect（v0 テンプレ / v1 GW-S1）
  → [advance | reread_same | close_book]
  → … → CLOSE → 次の 1 冊
```

---

## 状態

| ID | 内容 | 状態 |
|----|------|------|
| ALIVE-0 | 北極星 | ✅ |
| ALIVE-1 | `literary_wander` desire | ✅ 2026-06-25 |
| ALIVE-6 | LW-READ v0 | ✅ 2026-06-26 |
| ALIVE-2 | GW-S1 PAUSE | 📋 未配線 |
| ALIVE-3 | LW-5 UI（`active_work` 表示） | 📋 |
| ALIVE-4 | 翌朝 compose surface | 部分済 |
| ALIVE-5 | LW-7 Web 連鎖 | 📋 |

---

## v0 実装（済）

| ファイル | 内容 |
|----------|------|
| `presence-ui/.../aozora.py` | `ReadingState`、一冊完走、legacy マイグレーション |
| `direct_actions.py` | read / reflect / close、phase ルーティング |
| `plan.py` | inward: reflect / close を allowed に |
| `reading_prompts.py` | v0 テンプレ + GW-S1 草案 |

**状態ファイル**: `~/.claude/aozora_read_state.json`（`phase`, `active_work`, `passage_index` 等）

---

## 運用チェック

1. `.\scripts\restart-presence-ui.ps1` で反映
2. `autonomous-tick.log` で **read / reflect が交互**
3. `phase` が `read` ↔ `pause` を往復
4. GW-S1 は **まだ配線していない** — PAUSE はテンプレ

---

## 次（v1）

`reflect_on_aozora_passage_direct` 内で `run_silent_internal_turn` → JSON parse → `next_move` 反映。詳細 → [gw-silent.md](./gw-silent.md)

**縦スライス順**: ~~v0~~ ✅ → **GW-S1** → **LW-7** Web → LW-5 UI

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
