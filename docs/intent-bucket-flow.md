# Intent → Bucket → Flow — ツール選定強化計画

**合意**: 2026-06-17（まー）  
**状態**: 計画確立（実装は段階的）  
**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md)（A3 身体直実行）、[backlog-ma-home.md](./backlog-ma-home.md)

---

## 1. なぜこの計画か（きっかけ）

### 観測（2026-06-17）

| 経路 | 結果 |
|------|------|
| `POST /api/v1/autonomous-tick` + `miss_companion`（curl） | Surface で声が出る — gateway → `room-say` → Aivis |
| キオスク会話「何か say で喋って」 | LM Studio ログ: Gemma が **`mcp__tts__say` ではなく `ListMcpResourcesTool`** を選択 |
| `enabledMcpjsonServers` に `tts` ありのセッションでも | **How（手段）を LLM に丸投げ**すると迷子 |

**結論**: インフラ（TTS / kiosk / Aivis）は生きている。**ボトルネックは LLM へのツール名選定**。

### コミュニケーションモデル（まーの整理）

会話は次の繰り返し:

1. 文章の欠落を穴埋めして **5W1H を主観的に完成**させる  
2. 内容・目的を判断する  
3. **手段を選定**する  
4. 実際に動く  

ローカル LLM（Gemma）に ①〜④ を一度にやらせると、**How に着く頃にはコンテキストとツール山で迷子**になる（~46k トークン + 全 MCP ツール定義）。

**子供に指示を出す比喩**: 分解して一歩ずつ。LLM は **言葉と解釈**、身体は **フロー（gateway）**。

---

## 2. 設計原則

### 原則 A — LLM にツール名を選ばせない

`mcp__tts__say` / `mcp__wifi-cam__see` 等は **実装詳細**。判断の出力ではない。

ツール名選定を LLM に任せると、明示的なユーザー指示（「say で」）でも **無関係ツール**（`ListMcpResourcesTool` 等）を選ぶ確率が跳ね上がる。

### 原則 B — 三層で分離する

| 層 | 問い | 決めるもの | 誰が |
|----|------|------------|------|
| **Intent** | 何をする必要があるか？ | ニーズ（speech / observe / remember / defer …） | ルール優先、曖昧時のみ薄い LLM |
| **Bucket** | どう動く必要があるか？ | モダリティ（`speak`, `observe`, `remember` …） | **機械**（表引き） |
| **Flow** | 何を動かす必要があるか？ | アクチュエータ（Surface, カメラ, `:18900` …） | **gateway**（コード） |

MCP サーバーは **Flow の実装の一つ**。CLI `/talk` 用に `.mcp.json` からは削除しないが、**キオスク本線・日常 Native chat では LLM ctx に載せない**。

### 原則 C — Plan さんはすでに「粗い What」

`plan_response`（`interaction-orchestrator-mcp/plan.py`）は **deterministic and shallow** なルール表。LLM ではない。

- **得意**: 境界、深夜、自律 tick、`primary_move`、desire → `allowed_actions`（`act_autonomously` 時）
- **未対応**: 通常会話の「喋って」「見て」→ バケツ、`voice.speak`（`answer_directly` は **意図的に `speak=false`**）

新設するのは Plan の置き換えではなく、**Intent 層 + Bucket→Flow マップ**。

---

## 3. 現状アーキテクチャ（どこまで出来ているか）

```
まーの発話
  → hook（recall 注入 / social ingest）
  → gateway: compose（in-process）
  → gateway: plan（in-process）
  → [gap] 通常会話: LLM + 全 MCP ツール  ← ここが問題
  → gateway: 一部 deterministic（remember / see_prefetch / dismiss）
```

**自律 tick（済）** — 望ましい形の参考実装:

```
desires.json → compose → plan (act_autonomously, allowed_actions=[1手])
  → execute_autonomous_plan → bucket 相当の分岐 → gateway Flow
  → satisfy_desire / experience
```

**キオスク会話（ギャップ）** — plan 済みでも How を LLM に返している。

---

## 4. Plan さんの的確さ（期待値）

| 領域 | 評価 | 根拠 |
|------|------|------|
| 深夜・do_not_interrupt | ◎ | `benchmarks/human_response/` 11 fixtures |
| 自律 + dominant desire → 1 allowed_action | ◎ | A3d + ⑤a–d |
| 質問 → answer_directly | ○ | キーワード（？、どう、教えて） |
| 通常会話の身体指示 | ✗ | `allowed_actions` は `act_autonomously` 時のみ |
| 声 | ✗ 設計衝突 | `answer_directly` → `voice.speak=false`（SOUL「積極的 say」と逆） |

Plan を「賢くする」より、**Plan の出力の上に Intent→Bucket→Flow を載せる**。

---

## 5. バケツ一覧（v0）

バケツ名は **ツール名ではない**。gateway 内部の enum 想定。

| バケツ | 意味 | 典型トリガー |
|--------|------|----------------|
| `speak` | 声で届ける | 「喋って」「say で」、plan が voice 許可 |
| `observe` | 見る | 「見て」「外どう」、`see_prefetch` |
| `remember` | 記憶保存 | 「覚えて」、`persist_remember_intent` |
| `recall` | 想起（応答材料） | compose 済み / 明示 recall 要求 |
| `reflect` | 私的メモ | quiet hours / `write_private_reflection` |
| `browse` | 調べる | desire `browse_curiosity` / 明示 |
| `remind` | リマインド | due commitment |
| `defer` | 動かない | `stay_silent` / `defer` / boundary deny |
| `chat_only` | テキストのみ | デフォルト（身体不要） |

複数バケツが立つ場合は **優先表**で 1 手に絞る（自律 tick と同型）。

---

## 6. Bucket → Flow マッピング表（v0）

| バケツ | Gateway Flow（実装） | MCP（CLI 用・表の奥） |
|--------|----------------------|------------------------|
| `speak` | `deliver_speak_to_kiosk`（kiosk 優先）+ boundary | `mcp__tts__say` |
| `observe` | `see_prefetch` / `observe_room_direct` / preset look | `mcp__wifi-cam__see` 等 |
| `remember` | `persist_remember_intent` → `:18900` | `mcp__memory__remember` |
| `recall` | compose `relevant_memories` / `http_recall` | `mcp__memory__recall` |
| `reflect` | `write_private_reflection_direct` | `mcp__sociality__append_private_reflection` |
| `browse` | `web_search_direct` | — |
| `remind` | `remind_commitment_direct` | — |
| `defer` | なし | — |
| `chat_only` | なし | — |

**既存**: [gateway-direct-actions.md](./gateway-direct-actions.md) の allowed_action 表は **自律 tick 用の Bucket→Flow の部分実装**。

---

## 7. Intent 解決（`resolve_user_intent`）

Plan の**前または直後**に置く薄い層。

### 7.1 ルール優先（v0）

明示キーワードで即決（LLM 不要）:

| パターン | `wants` | `explicit_how` |
|----------|---------|----------------|
| say / 喋 / しゃべ / 声で | `speech` | `say` if 「say」含む |
| 見て / どう見える | `observe` | — |
| 覚えて / 記憶 | `remember` | — |

例: 「何か say でしゃべって」→ `{ wants: ["speech"], explicit_how: "say" }` — **子供でも一発でわかる要求**。

### 7.2 LLM フォールバック（任意・C12 接続）

**曖昧な一文だけ** JSON 分類（`desk|see|speech|chat` 等）。  
本番の主経路にはしない。taxonomy 設計・ログ diff 用。

### 7.3 Plan との合成

```
intent = resolve_user_intent(user_text)
plan   = plan_response(ctx, user_text)

effective_buckets = merge(intent, plan)
  - plan.stay_silent / defer → defer 勝ち
  - intent.wants_speech && !plan.boundary.quiet → speak バケツ
  - plan.act_autonomously → 既存 allowed_actions（変更なし）
```

`voice.speak` は **intent + plan 合成**で上書き（通常会話で speak 要求を反映）。

---

## 8. 会話ターンの目標フロー

```
まーの発話
  → compose
  → resolve_user_intent（ルール）
  → plan
  → merge → effective_buckets（最大1身体手 + chat）
  → LLM: 返答文のみ生成（MCP ツール JSON なし or 最小）
  → gateway: 返答確定後に Flow 実行（例: speak → room-say）
  → record_agent_experience / ingest
```

**ポイント**: Gemma は **③ Flow を選ばない**。返答テキストができたら gateway が `speak` バケツを実行。

---

## 9. 実装フェーズ

| Phase | 内容 | 受け入れ条件 |
|-------|------|----------------|
| **IBF-0** | 本ドキュメント + backlog リンク | まー合意 |
| **IBF-1** | `resolve_user_intent`（ルールのみ）+ 単体テスト | 「say で」→ `wants_speech` |
| **IBF-2** | compose/plan 合成: `voice.speak` 上書き + `[Action]` 注入 | plan が speak=false でも注入に speak 必須 |
| **IBF-3** | 会話ターン: 返答後 `deliver_speak_to_kiosk`（Gemma が say 呼ばなくてよい） | キオスクで「喋って」実戦 OK |
| **IBF-4** | `enabledMcpjsonServers` 日常 = `system-temperature` 固定の確認 | LM Studio ログに MCP 山が出ない |
| **IBF-5** | observe / remember を同一パイプラインに統合（既存 deterministic を `merge` 経由に） | バケツ表と実装一致 |
| **IBF-6** | 自律 tick: `allowed_action` をバケツ名にリネーム整理（任意） | ドキュメント・コード用語統一 |
| **IBF-7** | LLM intent 実験（オフライン diff） | plan vs LLM の一致率メモ |

**最初の一本**: **IBF-1 → IBF-2 → IBF-3**（speak だけで Surface 問題を閉じる）。

---

## 10. やらないこと（スコープ外）

- Gemma を賢くする / 大きい GPU を前提にする（手段選定を LLM に戻す）
- Plan を LLM 化する（deterministic の強みを捨てる）
- MCP サーバー実装の削除（CLI・デバッグ用に残す）
- 全ツールの完全自動マッピングを一度に（バケツ v0 から増やす）

---

## 11. 検証・観測

| 観測 | 方法 |
|------|------|
| Surface 发声 | キオスク「音声テスト」+ 会話「say で」 |
| LLM がツールを選んでない | LM Studio log: `tools` 配列が小さい / `mcp__*` tool_use なし |
| Plan 回帰 | `uv run pytest` orchestrator + `benchmarks/human_response` |
| Gateway 回帰 | `presence-ui` tests + `test-gateway-direct-actions.ps1` |

---

## 12. 用語集

| 用語 | 意味 |
|------|------|
| **Intent** | まー（+文脈）が求めているニーズの構造化表現 |
| **Bucket** | モダリティ。ツールに非依存 |
| **Flow** | gateway の Python/HTTP 実行経路 |
| **Plan** | `plan_response` の `primary_move` / initiative / voice |
| **allowed_action** | 自律 tick 用の旧バケツ名（段階的に Bucket と対齐） |

---

## 13. 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-06-17 | 初版 — ma-home 会話ログ分析・5W1H/Plan 議論を反映 |
