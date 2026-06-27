# OL5 — 予定消化で open loop 終了

**状態**: ✅ OL5-a/b 運用確認済（2026-06-27）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [architecture/open-loops-reminders.md](../architecture/open-loops-reminders.md)、[gw-silent.md](./gw-silent.md)

---

## 現状

| 層 | 内容 | 状態 |
|----|------|------|
| **作成** | GW-S2 OL-GATE — When / What / How が揃うときだけ loop | ✅（`PRESENCE_GW_S2_ENABLED=1`） |
| **seed** | loop 作成時に `completion_verbs[]` を `detail_json` へ | ✅ OL5-a（ヒューリスティック、`action_phrase` から） |
| **close** | ingest 再解析 `past_completion` + 保存 verbs の union 照合 | ✅ 運用確認済 |
| **fallback** | カレンダー日跨ぎ `close_stale_open_loops` | ✅ 従来どおり |

**ma-home 確認（2026-06-25）**: `list_open_loops` の `detail.completion_verbs` に例 `["行ってきた", "行った", "出かけてきた"]` が載ることを確認。

**ma-home 確認（2026-06-27）**: ingest「ちょっと早かったけど、ライブ、行ってきた」で loop `loop_ea4dbebeb3`（topic: 2026年6月27日、18:00にライブに行く）が `status=closed`、`detail_json.kind=ol5_completion`。

**修正（2026-06-27）**: ingest の `action_terms` を全 open loop に union していたため、ライブ close で肉じゃが loop も誤 close した → loop 固有 term のみ照合に変更（`0aa773e`）。

**作成側（v0 残）**: GW-S2 OFF 時は **いつ** だけで loop ができる（「また明日！」→ phatic loop）。本番は GW-S2 ON 推奨。

---

## 望ましい将来

予定 **消化** を発話や experience から検知 → 関連 topic の loop を close。

| 例 | v0（日跨ぎのみ） | OL5 後 |
|----|-----------------|--------|
| 角煮を作る | 日跨ぎまで open | 「角煮、作った」で close |
| 明日朝散歩 | 日跨ぎまで open | 「散歩行ってきた」で close |

---

## 設計要点

- dismiss（「忘れて」）とは別 — **成功完了**の肯定閉じ
- **完了フレーズはタスク依存（動的）**: topic から活動の核 + その活動に自然な完了表現
- **セット照合**: 行動語 + 完了語が **両方** 出現（「作った」単体では不可）

---

## 実装段階

| 段階 | 内容 | 状態 |
|------|------|------|
| v0 | 日跨ぎ stale のみ | ✅ |
| **OL5-a** | 作成時 `completion_verbs` ヒューリスティック seed | ✅ 2026-06-25 |
| **OL5-b** | ingest `past_completion` 再解析 + union close | ✅ 2026-06-27 運用確認 |
| **OL5-c** | GW-SILENT で LLM 完了語セット生成（seed より広い） | 📋 |

LM Studio 手動テスト（Gemma）で「散歩に行く」→ 完了フレーズ 10 個生成は **ルール単語リストより topic 展開が現実的** という根拠あり。詳細例は [archive/backlog-ma-home-full-2026-06-26.md](../archive/backlog-ma-home-full-2026-06-26.md) § OL5。

---

## 次の確認

1. 実発話（「行ってきた」「作った」）で open loop が **closed** になるか
2. GW-S2 ON で phatic 挨拶が loop にならないか
3. `relationship-mcp` reinstall は **`presence-ui` venv 内** — リポジトリ直下の `uv pip` では venv なしエラー

```powershell
cd presence-ui
uv pip install --reinstall "relationship-mcp @ file:///C:/Users/ma/src/embodied-claude/sociality-mcp/packages/relationship-mcp"
.\scripts\restart-presence-ui.ps1
```
