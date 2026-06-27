# 全文アーカイブ索引 — `backlog-ma-home-full-2026-06-26.md`

**目的**: 2026-06-26 整理前の全文（~1900 行）と、現行ドキュメントの対応表。  
**全文**: [backlog-ma-home-full-2026-06-26.md](./backlog-ma-home-full-2026-06-26.md)  
**いま触る**: [backlog-ma-home.md](../backlog-ma-home.md)

**2026-06-26 更新**: 優先度 低 まで含め、アーカイブ専用だった主要節を **tracks / architecture / ops** へ抜粋済み（下表「移行先」）。

---

## 設計の正（最初に読む）

| 文書 | 内容 |
|------|------|
| [cognitive-layers.md](../architecture/cognitive-layers.md) | **実装判断の正** — 表層/前頭葉、実装前 3 問 |
| [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md) | encode/retrieve 非対称 |
| [platform-ma-home.md](../architecture/platform-ma-home.md) | 8080・A 様子見・北極星 |

---

## セクション → 移行先（2026-06-26 抜粋完了）

| アーカイブ § | 移行先 |
|-------------|--------|
| 認知層・GW KV | [cognitive-layers.md](../architecture/cognitive-layers.md)、[gw-silent.md](../tracks/gw-silent.md) |
| MEM-8 | [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md) |
| MEM 4層・昇格・5e/5f/5k/7 | [mem-pipeline.md](../architecture/mem-pipeline.md) |
| VIS | [vis-health.md](../tracks/vis-health.md) |
| OBS | [obs.md](../tracks/obs.md) |
| CAM | [cam-tapo-ptz.md](../tracks/cam-tapo-ptz.md) |
| EAR | [ear.md](../tracks/ear.md) |
| GAPI | [gapi.md](../tracks/gapi.md) |
| WS-5 | [ws-5-spontaneous-search.md](../ops/ws-5-spontaneous-search.md) |
| A4 Outbound | [outbound-channels.md](../architecture/outbound-channels.md) |
| V / C 残 | [surface-vision.md](../tracks/surface-vision.md) |
| 手動スクリプト | [scripts-reference.md](../ops/scripts-reference.md) |
| ALIVE / LW（LW-0〜7 表・動機・チェックリスト含む） | [alive-lw-read.md](../tracks/alive-lw-read.md) |
| GW-SILENT / OL-GATE | [gw-silent.md](../tracks/gw-silent.md)、[open-loops-reminders.md](../architecture/open-loops-reminders.md) |
| OL5 | [ol5.md](../tracks/ol5.md) |
| IBF / Gateway | [intent-bucket-flow.md](../architecture/intent-bucket-flow.md)、[gateway-direct-actions.md](../architecture/gateway-direct-actions.md) |
| BIO / pulse | [heartbeat-loop.md](../architecture/heartbeat-loop.md) |
| WS-1〜2c | [ws-2-conversation-web-search.md](../ops/ws-2-conversation-web-search.md) |
| RP | [role-persistence-ma-home.md](../ops/role-persistence-ma-home.md) |
| K | [k-self-code.md](../tracks/k-self-code.md) |
| 8080 / A 様子見 | [platform-ma-home.md](../architecture/platform-ma-home.md) |

---

## まだ全文にしかない細部（必要時のみアーカイブへ）

| 内容 | 理由 |
|------|------|
| IBF ベンチマーク数値、OL Gemma 手動テスト全文 | 実装時の参考ログ |
| A4j 修正前の「おかしい」挙動の長文 | 履歴 |
| CAM H1–H8 仮説表の全行 | [cam-tapo-ptz.md](../tracks/cam-tapo-ptz.md) に要約済み |
| MEM-5 採点式の重み調整メモ | [mem-pipeline.md](../architecture/mem-pipeline.md) に要約済み |
| C11 回帰（crypto.randomUUID）の詳細 | [surface-vision.md](../tracks/surface-vision.md) に触れず — デバッグ時のみ全文 |
| Desire ⑤ 表の古い「未実装」行 | **誤り** — 済が正（下記） |
| exported-session / web_ui_design 由来の夢物語 | 歴史参照のみ |

---

## ステータス表記の注意（アーカイブ内矛盾）

| 箇所 | 信頼する方 |
|------|-----------|
| Desire ⑤b `cognitive_load` | **済** — `think_or_discuss_topic_direct` |
| MEM-8 「済（本文）」 | **概念済** — 8a/8c/8d 未 |
| IBF 「計画済」 | **IBF-0〜7 実装済** |
| MEM トラック「5a–5f-c 済」 | 5f・5k・7・8a/8d は **未** |

---

## アーカイブ内アンカー（全文検索用）

| 見出しキーワード | 用途 |
|-----------------|------|
| `ALIVE — 生きてる感` | 北極星縦スライス |
| `BIO-8 — Somatic` | 器官・env |
| `MEM-8 — encode` | 非対称の完全版 |
| `MEM-8b-lite` | compose tier（抜粋済） |
| `GW-SILENT` | 黙考完全版 |
| `手動・デバッグ早見` | スクリプト（抜粋済） |

---

## 運用ルール

1. **新合意** → まず tracks か architecture に 1 枚。アーカイブは追記しない（スナップショット固定）。
2. **Linksee / handoff**: 重複 OK・抜け NG（[handoffs/README.md](../handoffs/README.md)）。
3. 実装完了 → [backlog-archive-ma-home.md](../backlog-archive-ma-home.md) に 1 行。

---

## 漏れ監査（2026-06-26）— 完了

| 優先 | 項目 | 状態 |
|------|------|------|
| 高 | 認知層方針 | ✅ |
| 高 | MEM-8 | ✅ |
| 高 | OL-GATE / GW | ✅（既存） |
| 中 | VIS | ✅ `vis-health.md` |
| 中 | MEM パイプライン | ✅ `mem-pipeline.md` |
| 中 | スクリプト早見 | ✅ `scripts-reference.md` |
| 低 | OBS / CAM / EAR / GAPI | ✅ tracks |
| 低 | WS-5 / Outbound / V | ✅ ops + architecture + tracks |
| 低 | 8080 / A 様子見 | ✅ `platform-ma-home.md` |
