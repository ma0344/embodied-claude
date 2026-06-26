# OL5 — 予定消化で open loop 終了

**状態**: 📋 計画済（GW-S1 依存）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [architecture/open-loops-reminders.md](../architecture/open-loops-reminders.md)、[gw-silent.md](./gw-silent.md)

---

## 現状（暫定 OK）

open loop は **カレンダー日** が過ぎたら `close_stale_open_loops` で close。「角煮を作った」「散歩行ってきた」では閉じない。

---

## 望ましい将来

予定 **消化** を発話や experience から検知 → 関連 topic の loop を close。

| 例 | 今 | OL5 後 |
|----|-----|--------|
| 角煮を作る | 日跨ぎまで open | 「角煮、作った」で close |
| 明日朝散歩 | 日跨ぎまで open | 「散歩行ってきた」で close |

---

## 設計要点

- dismiss（「忘れて」）とは別 — **成功完了**の肯定閉じ
- **完了フレーズはタスク依存（動的）**: topic から活動の核 + その活動に自然な完了表現
- **セット照合**: 行動語 + 完了語が **両方** 出現（「作った」単体では不可）

---

## 実装イメージ（v1）

loop 作成時に **GW-SILENT** で `action_terms[]` + `completion_verbs[]` を生成 → `detail_json` に保存 → ingest / experience で overlap 検知。

| 段階 | 内容 |
|------|------|
| v0 | 日跨ぎ stale のみ（**現状**） |
| v1 | GW-S1 で動的語セット生成 + 照合 |

LM Studio 手動テスト（Gemma）で「散歩に行く」→ 完了フレーズ 10 個生成は **ルール単語リストより topic 展開が現実的** という根拠あり。詳細例は [archive/backlog-ma-home-full-2026-06-26.md](../archive/backlog-ma-home-full-2026-06-26.md) § OL5。
