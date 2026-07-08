# Gateway 直実行 — 判断は compose/plan、身体は MCP 外

**合意**: 2026-06-14（まー）  
**方針**: オリジナル embodied-claude の判断/行動機構（compose / plan / stores / boundary / desires）は維持。**実行**は LLM→MCP ではなく gateway が代行してよい（remember 直実行と同型）。

**LLM 判断の原則（2026-06-30）**: 不可逆な副作用は **一発 e4b 任せにしない** — [Propose → Confirm → Execute](./llm-propose-confirm-execute.md)（GAPI-7b · OL6/OL7 · 今後の TEMP-C5 等）。

---

## すでに gateway 直実行済み

| 機能 | 実装 | MCP 不要 |
|------|------|----------|
| remember | `deterministic_memory.persist_remember_intent` → `:18900` | ✓ |
| 記憶リスト | `fetch_memory_list` → direct / prefetch | ✓ |
| compose recall | `HttpMemoryAdapter` in orchestrator | ✓ |
| compose / plan | `social_chat.intercept_chat_request` in-process | ✓ |
| human / agent ingest | `room_ingest` | ✓ |

**設計（未実装）**: **黙考ルート** — 表の会話と同じ Claude セッション + stable `appendSystemPrompt` で internal turn を回し、まーに見せず構造化結果だけ stores へ。OL5 完了語セット生成の第一用途。→ [tracks/gw-silent.md](../tracks/gw-silent.md)

参照: `presence-ui/src/presence_ui/gateway/deterministic_memory.py`

---

## これから gateway に寄せる（身体・自律）

plan の `initiative.allowed_actions`（`plan.py`）を gateway が解釈し、**boundary 評価後**に Python/HTTP で実行する。

| allowed_action | 直実行候補 | 備考 |
|----------------|-----------|------|
| `camera_look_around` | wifi-cam `look_around` + `see` | observe_room |
| `camera_look_outside` | USB webcam（外・窓）優先、失敗時 Tapo preset | look_outside |
| `talk_to_companion` | tts `say`（boundary OK 時） | miss_companion |
| `remind_commitment` | outbound + tts、then `complete_commitment` | OL2、due commitment 優先 |
| `write_private_reflection` | orchestrator `append_private_reflection` | quiet hours |
| `web_search` | DuckDuckGo instant API + `:18900/remember` | browse_curiosity |
| `read_aozora_passage` | Aozora Bunko HTML (Shift_JIS) + remember + private reflection | quiet + cognitive_load |
| `think_or_discuss_topic` | private reflection（open loops / prompt からメモ） | cognitive_load |
| `recall_memories` | `:18900/recall` + private note | identity_coherence |
| （followup）`satisfy_desire` | desire_updater / memory marker | 1 action 1 satisfy |

**触らない**: compose / plan のルール本体。MCP サーバー実装も `.mcp.json` からは削除しない（CLI `/talk` 用に残す）。

**既存**: [gateway-direct-actions.md](./gateway-direct-actions.md) の allowed_action 表は §6.1 の抜粋。**詳細・正規の対応表は [intent-bucket-flow.md §6](./intent-bucket-flow.md#6-用語対応表--allowed_action--バケツ--flowibf-6a)**。

---

## フロー（自律 tick / act_autonomously）

```
desires.json
  → compose (in-process) → plan (primary_move=act_autonomously, allowed_actions=[…])
  → gateway: evaluate_action (boundary store)
  → gateway: execute bounded action (see / say / private note)
  → record_agent_experience + satisfy_desire + room_activity
  → LLM には結果サマリだけ注入（または silent / 短い報告）
```

8090 に `POST /api/autonomous-tick`（仮）を足すか、既存 intercept に `autonomous_trigger` + empty message を正式化。

---

## MCP 削減との関係

- **日常 chat**: `enabledMcpjsonServers` = `system-temperature` のまま
- **手動プロファイル切替**: 移行期の逃げ道。gateway 直実行が揃えば **voice/see 用にまーが settings を触る必要はなくなる**
- **トークン**: wifi-cam / sociality / memory の tool JSON が LLM ctx から消える

---

## 実装順（提案）

1. [x] **A3a** `write_private_reflection` gateway 直実行（`direct_actions.py` + `social_chat` intercept）
2. [x] **A3b** `observe_room` — `camera_look_around`（**OBS-TICK-0**: caption/remember 停止 · desire のみ → [obs-tick-encode.md](../tracks/obs-tick-encode.md)）
3. [x] **A3c** `miss_companion` — boundary → `talk_to_companion_direct` + `services/tts.py`
4. [x] **A3d** 自律 tick — `POST /api/v1/autonomous-tick` + `satisfy_desire_direct`
5. [x] **A3e** スモーク — autonomous-tick + observe_room（2026-06-14）
6. [x] **A3f** **vision prefetch（A）** — 会話「見て」→ capture + LM Studio caption → `[vision_prefetch]` 通訳 → forward
7. [x] **A3g** **desire see（B）** — `look_outside` / preset → caption → remember（`observe_room` は OBS-TICK-0 で look のみ）

### カメラ向き（named presets）

`wifi-cam-mcp/.env` または `presence-ui.local.env`:

```env
TAPO_WINDOW_PRESET=1
TAPO_MADESK_PRESET=2
TAPO_DINING_PRESET=3
# または PRESENCE_CAMERA_*_PRESET= で上書き
```

| 場所 | 会話例 | preset env |
|------|--------|------------|
| 窓/外 | 「窓の外どう？」 | `TAPO_WINDOW_PRESET` |
| まーのデスク | 「まーのデスク見て」 | `TAPO_MADESK_PRESET` |
| ダイニング | 「ダイニングの様子どう？」 | `TAPO_DINING_PRESET` |

`look_outside` desire と会話の「外／窓／天気」は **Tapo window preset**（`TAPO_WINDOW_PRESET` · `mode=window`）。USB 外カメラ経路は **廃止**（2026-07-06）。

```env
# 窓・外は Tapo preset のみ（USB は無効）
TAPO_WINDOW_PRESET=<onvif-preset-id>
```

### 「忘れて」→ open loop を閉じる

まーが **中止 / キャンセル / 忘れて** と言ったとき、relationship の open loop を `closed` にし、
compose 前に `[open_loop_dismiss]` を注入する（plan が再提示しにくくする）。

例: 「PRのレビューは中止。その予定は忘れて。」→ `pr review` open loop を閉じ、
文言が一致する **active commitment** を `cancelled` にする。

環境変数: `PRESENCE_GATEWAY_VISION_PREFETCH=1`（既定 ON）。`0` で会話 A のみ無効（B は caption 継続）。

### API

```powershell
# 自律 tick（compose → plan → 1 bounded action）
Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -ContentType application/json `
  -Body '{"person_id":"ma","trigger":"manual"}' | ConvertTo-Json

# 全経路スモーク（observe_room は ~45s、TTS 未設定なら miss_companion は自動 skip）
.\scripts\test-gateway-direct-actions.ps1

# TTS 要: tts-mcp/.env（ELEVENLABS_API_KEY または VOICEVOX_URL）
#   または ~/.config/embodied-claude/presence-ui.local.env に同キーを記載
Copy-Item tts-mcp\.env.example tts-mcp\.env   # 初回のみ。API キーを編集してから restart

# 個別強制（compose/plan は走るが実行は smoke_action 指定）
Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -ContentType application/json `
  -Body '{"smoke_action":"observe_room","trigger":"smoke"}' | ConvertTo-Json

Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -ContentType application/json `
  -Body '{"smoke_action":"miss_companion","speech_text":"まー、おる？"}' | ConvertTo-Json
```

環境変数: `PRESENCE_GATEWAY_DIRECT_ACTIONS=1`（既定 ON）。`0` で従来 MCP 経路に戻す。

**青空文庫（LW-1）**:

```env
# 読書位置の state（既定 ~/.claude/aozora_read_state.json）
PRESENCE_AOZORA_STATE_PATH=

# 作品リスト JSON（省略時: 羅生門 / 妙な話 / 侏儒の言葉）
PRESENCE_AOZORA_WORKS=
```

スモーク:

```powershell
Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -ContentType application/json `
  -Body '{"smoke_action":"read_aozora","trigger":"smoke"}' | ConvertTo-Json
```

デプロイ: `.\scripts\sync-presence-deps.ps1` → `.\scripts\restart-presence-ui.ps1`

---

## 関連

- [ops/lmstudio-kv-cache.md](../ops/lmstudio-kv-cache.md) — daily MCP プロファイル
- [backlog-ma-home.md](../backlog-ma-home.md) — ダッシュボード
- [tracks/alive-lw-read.md](../tracks/alive-lw-read.md) — LW-READ v0/v1
- [mission-A_Investigation-Report.md](./mission-A_Investigation-Report.md) — compose 経路
