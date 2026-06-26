# GW-SILENT — 黙考ルート（silent internal turn）

**状態**: 📋 プロンプト済・**S1 未配線**  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**第一用途**: LW-READ PAUSE（v1）、OL5 完了語セット生成  
**ループ上の位置**: BIO Heartbeat の **interpret** 層（`notice → interpret → choose → act → remember → schedule`）  
**関連**: [architecture/gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[ops/lmstudio-kv-cache.md](../ops/lmstudio-kv-cache.md)、[ol5.md](./ol5.md)

---

## なぜ GW が優先か

LW（読書）、BIO Heartbeat（`notice→interpret→choose→act→remember→schedule`）、将来の **K**（自己改修）は同じループ構造。**GW-SILENT = 共有の interpret 層**。B2 のような機械オペより根本的。

---

## やりたいこと

まーに見せないが **こより本人の文脈・人格・KV prefix** で LM に考えさせ、結果だけ gateway が parse して stores に保存する。

**別プレーンの単発 API は使わない** — prefix がコールドになり再読み込みリスクが高い。

---

## 本線経路

```
まー発話（通常ターン N）
  → ingest / compose / plan → 表向き返答
  → [背景] 同じ session_id（--resume）で internal turn N+1
       message: [gateway_internal] + 構造化タスク
       appendSystemPrompt: build_gateway_stable_append()（毎ターン同一）
       forward=False — UI に流さない
  → gateway が JSON parse → stores / detail_json
```

| 経路 | KV 再利用 | まーに見える |
|------|-----------|--------------|
| Native chat | ◎ | はい |
| `write_private_reflection`（現状） | — | いいえ（テンプレ） |
| **GW-SILENT** | ◎（同一セッション） | いいえ |

---

## 実装候補

| ID | 内容 | 状態 |
|----|------|------|
| GW-S1 | `run_silent_internal_turn(session_id, task, schema)` | 📋 未 |
| GW-S1-prompt | LW-READ PAUSE 用 `build_gw_s1_pause_task` | ✅ 2026-06-26 |
| GW-S2 | ingest 後 5W1H 抽出 + loop 作成判定 + OL5 語セット enqueue | 📋 |
| GW-S3 | 共通 JSON parse / validate | 📋 |

コード: `presence-ui/.../reading_prompts.py`（`PAUSE_RESPONSE_SCHEMA`, `FELT_HINTS`）

---

## 運用メモ

- 表返答の **後** に background 実行
- LM Studio **Concurrent Predictions = 1** を維持
- internal turn は **MCP スリム**（tool 定義を毎回載せない）
- 参照: `social_chat.py`（`stream_silent_response`）、`prompt_injection.py`

---

## 他用途（未着手）

| 用途 | 出力先 |
|------|--------|
| **OL-GATE** 5W1H 抽出 → loop 作るか | `open_loops` or 作らない（下記） |
| OL5 完了語セット | `open_loops.detail_json` |
| OL2 曖昧日付補完 | `needs_date_confirmation` |
| MEM 多視点 encode | gist / 視点ラベル |
| 夜間 digest 前処理 | トピック正規化 |

### GW-S2 — OL-GATE（When / What / How 抽出）

ingest 直後の internal turn。**不足を推測で補わない** — 文中に現れる **いつ・何を・どうする** の語だけ抜き出す。フォローアップとして成立しなければ `is_follow_up_task: false` + `ineligibility_reason`。

**手動スモーク v2（2026-06-26, `google/gemma-4-12b-qat`）**

| 例文 | temporal | object | action | `is_follow_up_task` | メモ |
|------|----------|--------|--------|---------------------|------|
| いつも一緒にいたかった | いつも | 一緒に | いたかった | **false** | 願望・「いつも」はタスクの When ではない |
| 明日、角煮を作る | 明日 | 角煮を | 作る | **true** | loop 候補 |
| 昨日、ロバがコケた | 昨日 | ロバが | コケた | **true** | 抽出は可。**過去** → open loop ではなく remember/STM 側 |
| また明日！ | 明日 | — | — | **false** | phatic・挨拶 |

**責務分担**

| 層 | フィールド | 誰が決める |
|----|-----------|-----------|
| LLM（黙考） | `utterance`, `temporal_phrase`, `object_phrase`, `action_phrase`, `is_follow_up_task`, `ineligibility_reason` | Gemma |
| Gateway（コード） | `resolved_date`, `is_future_commitment`, `create_open_loop`, `loop_topic`, `action_terms`, `completion_verbs` | `relationship_mcp` + `date_resolution` |

```
create_open_loop = is_follow_up_task && is_future_commitment
```

`is_follow_up_task=true` でも **昨日** は `is_future_commitment=false` → loop なし。挨拶は object/action 欠落で `is_follow_up_task=false`。

**LLM 出力 schema（`OL_GATE_EXTRACT_SCHEMA`）**

```json
{
  "utterance": "明日、角煮を作る",
  "temporal_phrase": "明日",
  "object_phrase": "角煮を",
  "action_phrase": "作る",
  "is_follow_up_task": true,
  "ineligibility_reason": null
}
```

```json
{
  "utterance": "また明日！",
  "temporal_phrase": "明日",
  "object_phrase": null,
  "action_phrase": null,
  "is_follow_up_task": false,
  "ineligibility_reason": "挨拶であり、対象と動作を表す語が含まれない"
}
```

**Gateway がマージしたあと（DB 書き込み用）**

```json
{
  "utterance": "明日、角煮を作る",
  "temporal_phrase": "明日",
  "object_phrase": "角煮を",
  "action_phrase": "作る",
  "is_follow_up_task": true,
  "ineligibility_reason": null,
  "resolved_date": "2026-06-27",
  "is_future_commitment": true,
  "create_open_loop": true,
  "loop_topic": "明日、角煮を作る",
  "action_terms": ["角煮"],
  "completion_verbs": ["作った", "できた"]
}
```

プロンプト要件: **推測禁止**・JSON のみ・不適格なら `ineligibility_reason` に理由（空なら `null`）。Who/Where は聞かない。

`action_terms` / `completion_verbs` は `create_open_loop=true` のとき同ターンで載せ OL5 close に使う。

詳細 → [open-loops-reminders.md § OL-GATE](../architecture/open-loops-reminders.md#ol-gate--loop-作成条件設計メモ合意-2026-06-26)

### 検討 — `utterance_kind` 三分類（未採用）

英訳を挟んで **予定 / 予定完了 / それ以外** に分ける案。同一 internal turn で `OL_GATE_EXTRACT` と併せるか、英訳はモデル内部のみ（JSON に出さない）かは未決。

| `utterance_kind` | 例 | gateway |
|------------------|-----|---------|
| `future_commitment` | 明日、角煮を作る | `create_open_loop` 候補 |
| `past_completion` | 角煮、作った / 散歩行ってきた | OL5 close 候補（既存 loop 照合） |
| `other` | また明日！ / いつも一緒に… | loop も close もしない |

**賛成する理由**: OL-GATE（作成）と OL5（消化）を **1 発話タイプ**で切れる。`昨日、ロバがコケた` は `other` または `past_report`（remember 側）に落としやすい。

**英訳ステップの是非**: Gemma は日本語プロンプトで v2 スモーク済み → **必須ではない**。英訳は (a) プロンプト内の思考用ガイド、または (b) 曖昧例だけ二段、程度でよい。JSON フィールドは英語 enum のまま（`future_commitment` 等）、発話は `utterance` で日本語保持。

**本線案**: 英訳なしで LLM に `utterance_kind` を直接返させる。`is_follow_up_task` は `future_commitment` の部分集合（temporal+object+action が揃う場合のみ true）。

---

## v1 判断ポイント（まー）

- PAUSE をテンプレのまま様子見するか
- GW-S1 を配線して `next_move` / `felt` / `followup_query` を本物にするか
- セッション無し tick 時のフォールバック（rules vs 次 chat まとめて）
