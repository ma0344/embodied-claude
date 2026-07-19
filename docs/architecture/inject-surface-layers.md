# 注入の層 — 表層 / 表層に近い / Deep

**合意**: 2026-07-18（まー — 注入ダンプ棚卸し · avoid→profile 後）  
**地位**: `gateway_turn_context` / compose compact に載せる情報の **層分けの正**  
**関連**: [cognitive-layers.md](./cognitive-layers.md)、[tracks/surface-direct-llm.md](../tracks/surface-direct-llm.md)、[tracks/spontaneity.md](../tracks/spontaneity.md)、[ops/role-persistence-ma-home.md](../ops/role-persistence-ma-home.md)

認知層（表層 LLM vs 前頭葉 vs 感覚）とは別軸。こちらは **「今ターンのプロンプトに何を載せるか」** の語彙。

---

## 一言

| 層 | 意味 | まー向けに口に出すか |
|----|------|---------------------|
| **表層** | 今ターンの返答に直結。読まないとスレが切れる | 出す（または契約で必須） |
| **表層に近い** | 知ってるが常時は喋らない（know ≠ speak） | 条件付きだけ |
| **Deep** | 毎ターン繰り返さない常時規範（SOUL.core 等） | 振る舞いの土台。Must avoid に再掲しない |

**セッション内の会話は LTM ではない。** 同じ `session_id` の room transcript の **再注入**（下 §）。

---

## セッション保持（表層の本流）

```
まー/こより発話
  → social.db events (human_utterance / agent_utterance + session_id)
  → SqliteRoomSessionAdapter.load_transcript
  → compose session_history
       ├─ [recent_room_context]  … gateway_turn_context 内（Surface Direct は全文）
       └─ LM Studio messages[] … role=user/assistant、直近 N（既定 12）
```

| 置き場 | コード | 上限の目安 |
|--------|--------|------------|
| 永続 | `social.db` events | adapter 既定 500 |
| 注入テキスト | compose `[recent_room_context]` | lite compose / Tier 3 で trim 可 |
| チャット API | `build_surface_chat_messages` | `PRESENCE_SURFACE_HISTORY_TURNS`（既定 12） |

- **Must include** の「continue THIS room's thread」は、この再注入を読めという契約。
- **跨 session** は memory_bridge / LTM / gists（cue 時）。room transcript と混ぜない。
- Legacy Claude resume 時だけ compact は arc 要約（JSONL が本体）。Surface Direct は全文。

詳細 → [surface-direct-llm.md § プロンプト構成](../tracks/surface-direct-llm.md#プロンプト構成cc-append-の移植)

---

## ダンプ語彙での固定（2026-07-18）

実注入ブロック名で層を固定する。

### 表層（毎ターンの返答用）

| ブロック | 役割 |
|----------|------|
| `[Must include]` / `[Must avoid]`（**パス固有のみ**） | 契約。定番禁止は Deep へ移済み |
| `[Social move]` / `[Action]` | 今ターンの一手 |
| `[response_contract]` | **薄い念押し** — `treat_user_as` 短札 + `initiative` / `max_clarifying`。定番 prefer・口調は Deep（SOUL）。quiet/autonomous 差分だけ厚くなる |
| `[recent_room_context]` | **この部屋の台本**（本流） |
| 今ターンの生発話 | user 末尾 |

### 表層に近い（知ってるが喋らへん）

| ブロック | 役割 |
|----------|------|
| `[somatic_state]` | **異常時のみ**詳述（Encode広く≠Inject狭く）。正常時は要約行 `somatic=ok` のみ。自発の「問題ないでぇ」はしない；まーから調子・異常を聞かれたときだけ口にしてよい |
| `[calendar_expectations — background only]` | S2 · know≠speak。聞かれた／リマインド経路のときだけ言及 |
| desires の数値・discomfort | 判断・自律の材料。会話のネタにしないのが既定 |
| `Relevant memories: N (mentionable: 0)` | 件数だけ見える状態。中身は mentionable 時のみ表層 |
| soft status / schedule_facts（条件付き） | 経路が開いたときだけ厚くする |

### Deep（常時・再掲しない）

| 置き場 | 内容 |
|--------|------|
| `presets/koyori-SOUL.core.md`（stable append） | 口調・**常時禁止**（敬語・cheerleading・physical co-action・TTS/tools meta 等） |
| LM System は空 | SOUL は gateway append のみ（二重注入回避） |

### 表層ではない（紛らわしい近傍）

| ブロック | 正体 |
|----------|------|
| `[stm_recent]` | 短期バッファ。**部屋の台本ではない**。episode_close / tick テンプレは注入スキップ（TRIM） |
| `[recent_experiences]` | 経験ログ（room_view / autonomous 等）。会話履歴の代替にしない |
| `[memory_bridge]` / mentionable 食事カード | **跨 session の向きつき短冊**（例: 麺類（蕎麦）の日付付き記録）。巨大 KG ではない → [spontaneity 向きつき短冊](../tracks/spontaneity.md#向きつき短冊ネットワーク合意-2026-07-18) |

---

## ノイズ削減（INJECT-TRIM · 2026-07-18 実装）

| 順 | 対象 | 実装 |
|----|------|------|
| **1** | STM autonomous テンプレ + **episode_close 会話** | `should_skip_stm_surface_inject` — DB/Dreaming は残し、`[stm_recent]` から除外。台本は room events / messages[] が本流なので episode_close 対話の再注入はしない |
| **2** | `recent_experiences` room_view | OBS-TICK `Room view: <scene>` 同士も collapse。英語行は CJK Jaccard が効かなかった穴を塞いだ |
| **3** | desires 常時フル | compact は dominant + discomfort≥0.5 を最大2本 |

**残リスク**

- `messages[]` 12 turns と `[recent_room_context]` 全文の二重（長い部屋で効く）— 別チケット
- 日本語 layout 描写と英語 OBS-TICK が別クラスタのまま並ぶことはありうる

トラック名: **INJECT-TRIM**（v0 済）。

---

## 既にやったこと（同日）

- 定番 Must avoid → SOUL.core Deep（compose `ma` は `avoid=[]`、パス固有のみ残す）
- `person_profile_gists` → cue 時のみ表層
- INJECT-TRIM v0（上表）
- `[response_contract]` 薄型化 — 定番 prefer 削除、`treat_user_as: まー（友人）/ こより` + initiative のみ
- MEM-8h bridge — vision 出口除外 · cue 条のみ · 食事 fact encode（episode_close）

---

## 判断の短い式

1. **この部屋の直前の発話か？** → 表層（room transcript）。LTM にも episode_close 注入にも頼らない。
2. **知ってるが常時は言わへんか？** → 表層に近い（calendar_expectations が典型）。
3. **毎ターン同じ禁止・口調か？** → Deep（SOUL.core）。Must avoid に繰り返さない。
4. **STM / experiences / desires 全文は「台本」か？** → 違う。間引き対象（TRIM 済み）。
