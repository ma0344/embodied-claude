# GW-SILENT — 黙考ルート（silent internal turn）

**状態**: 📋 プロンプト済・**S1 未配線**  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**第一用途**: LW-READ PAUSE（v1）、OL5 完了語セット生成  
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
| GW-S2 | ingest 後「新規 open loop」→ GW-S1 enqueue | 📋 |
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
| OL5 完了語セット | `open_loops.detail_json` |
| OL2 曖昧日付補完 | `needs_date_confirmation` |
| MEM 多視点 encode | gist / 視点ラベル |
| 夜間 digest 前処理 | トピック正規化 |

---

## v1 判断ポイント（まー）

- PAUSE をテンプレのまま様子見するか
- GW-S1 を配線して `next_move` / `felt` / `followup_query` を本物にするか
- セッション無し tick 時のフォールバック（rules vs 次 chat まとめて）
