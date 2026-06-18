# HeartbeatLoop — 生物らしい振る舞い（合意 2026-06-17）

**きっかけ**: MCP 削減・gateway 直実行の議論。MCP は手段に過ぎず、本質は **経験が次の行動と次の起きる時刻に閉じるか**。固定 15 分 cron だけでは「こよりが次にいつ起きるか決める」感が弱い。

**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md)、[intent-bucket-flow.md](./intent-bucket-flow.md)、[VISION.md](./VISION.md)

---

## 合意した方針

| 論点 | 決定 |
|------|------|
| MCP は必須か | **いいえ**。ツール JSON を LLM に見せる配線の一つだっただけ |
| 判断者 | **Gateway / compose / plan / ルール** がいつ・何を。LLM は **どう言うか・意味づけ** |
| Tick の時刻 | **こより（コード）が `next_wake_at` を決める**。OS 15 分 Task はセーフティネット |
| 記憶の深い処理 | `recall_divergent` / `consolidate` は **HTTP + gateway**。LLM にツール選択させない |
| ロボット化の回避 | 反射は gateway、**surprise と育ち**は注入された記憶 + experience + interpretation_shift |

---

## HeartbeatLoop（1 本のループ）

```
wake
  → notice    … ingest / desire 更新
  → interpret … compose（記憶・関係・experience）
  → choose    … plan（黙る / 答える / 自律1手）
  → act       … gateway 直実行 or LLM（言葉のみ）
  → remember  … record_agent_experience / remember HTTP / consolidate
  → schedule  … agent_pulse.json に next_wake_at を書く
```

### 経路の統一

| 経路 | 実装 |
|------|------|
| キオスク会話 | `social_chat` intercept → LLM → **`heartbeat.record.finalize_chat_turn`** |
| 自律 tick | `run_autonomous_tick` → **`heartbeat.schedule.apply_pulse_after_tick`** |
| 起動装置 | **`PulseRunner`**（presence-ui 内）+ `EmbodiedClaude-AutonomousTick`（max フォールバック） |

---

## 判断者マトリクス

| 決定 | 誰 | MCP |
|------|-----|-----|
| いつ起きるか | `compute_next_pulse`（desire + plan.move + quiet hours） | 不要 |
| 自律の 1 手 | `plan.initiative.allowed_actions` → `direct_actions` | 不要 |
| 通常 recall | hook / compose → `:18900/recall` | 不要 |
| 深い recall | トリガー時 → `:18900/recall/divergent` → compose 注入 | 不要 |
| 記憶統合 | 深夜帯 / pulse wake → `:18900/consolidate` | 不要 |
| 返答文 | Gemma（strict MCP・注入文脈のみ） | 不要 |
| CLI 開発・探索 | 任意で MCP プロファイル | 任意 |

---

## 永続状態

`~/.claude/presence-ui/agent_pulse.json`:

```json
{
  "next_wake_at": "2026-06-17T23:40:00+09:00",
  "reason": "chat_turn; miss_companion elevated",
  "last_wake_at": "...",
  "last_action": "agent_response",
  "dominant_desire": "miss_companion",
  "last_consolidate_at": "..."
}
```

環境変数:

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_PULSE_RUNNER` | `1` | presence-ui 内 PulseRunner |
| `PRESENCE_PULSE_MIN_SEC` | `300` | 最短 sleep |
| `PRESENCE_PULSE_MAX_SEC` | `21600` | 最長 sleep（6h） |
| `PRESENCE_PULSE_USE_DIVERGENT` | `1` | 自律 recall で divergent HTTP |

---

## Somatic loop（神経系・BIO-8）

HeartbeatLoop（いつ起きるか・何をするか）に **直交する層**。器官の正常ベースラインと今の差分で違和感を検知し、反射→確認→叙述→助けを求める。

| 器官 | v0 |
|------|-----|
| 目 | capture / vision caption |
| 耳 | listen（後続） |
| 声 | TTS health |
| 考え | memory HTTP health |

実装フェーズ: **BIO-8a**（報告）→ **8b**（レジストリ + probe）→ **8c**（compose/plan で言うべきか）→ **8d**（横断 escalation）。  
詳細は [backlog-ma-home.md](./backlog-ma-home.md) の BIO-8 節。

---

## 実装フェーズ（backlog BIO）

| ID | 内容 | 状態 |
|----|------|------|
| BIO-0 | 本文書 + backlog | 進行中 |
| BIO-1 | `agent_pulse` + PulseRunner | 進行中 |
| BIO-2 | native chat 返答後 `finalize_chat_turn` | 進行中 |
| BIO-3 | memory HTTP `/recall/divergent` `/consolidate` | 進行中 |
| BIO-4 | 自律 recall → divergent、深夜 consolidate | 進行中 |
| BIO-5 | `plan.pulse_schedule` / LLM 微調整（任意） | 未 |
| BIO-6 | `/talk` → gateway API 一本化（CLI） | **済** |
| BIO-7 | `interpretation_shift` 返答後フック | **済** |
| BIO-8a | Somatic — 目の不調を experience + ステータスに報告 | **済** |
| BIO-8b | Somatic — `body_state` + pulse probe | **済** |
| BIO-8c | Somatic — compose/plan 叙述判断 | **済** |
| BIO-8d | Somatic — 複数器官 escalation | **済** |
| MEM-0 | 記憶 4 層 + Dreaming 昇格（backlog） | **済** |
| MEM-1〜2 | STM / エピソード締め（WM→STM） | 未 |
| MEM-3〜4 | Dreaming / 朝注入 | 未 |
| MEM-5〜6 | LTM 整理 / Deep 昇格 | 未 |
| MEM-7 | JSONL ライフサイクル（hide≠削除・自動退避） | 未（MEM-3 後） |

**次トラック（合意 2026-06-18）**: **MEM**（セッション跨ぎ・Dreaming）。詳細 → [backlog-ma-home.md](./backlog-ma-home.md) MEM 節。

---

## 成功の物差し（VISION より）

- まーとの会話が **続き・覚え・文脈を持つ**
- こよりが **自分から次のタイミングを決めて動く**（ログに reason 付き）
- 技術（MCP 山・固定 cron）が **関係の邪魔をしない**
