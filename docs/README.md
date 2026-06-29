# docs/ — 読み方ガイド

embodied-claude（ma-home / こより）の運用・設計ドキュメント。**まずここから**。

---

## いつ何を読むか

| 状況 | 読むもの |
|------|----------|
| **いま何をすべきか** | [backlog-ma-home.md](./backlog-ma-home.md)（ダッシュボード） |
| **なぜこのプロジェクトか** | [VISION.md](./VISION.md) |
| **MCP・設備の使い方** | [CLAUDE.md](../CLAUDE.md)（リポジトリ直下） |
| **青空読書・生きてる感** | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **黙考ルート（GW-S1）** | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **Gateway / 自律 tick の設計** | [architecture/gateway-direct-actions.md](./architecture/gateway-direct-actions.md) |
| **Heartbeat・pulse** | [architecture/heartbeat-loop.md](./architecture/heartbeat-loop.md) |
| **認知層・設計方針** | [architecture/cognitive-layers.md](./architecture/cognitive-layers.md) |
| **相対日・deixis / TEMP** | [tracks/utterance-anchoring.md](./tracks/utterance-anchoring.md) |
| **open loop / リマインド / close** | [architecture/open-loops-reminders.md](./architecture/open-loops-reminders.md) · [tracks/ol5.md](./tracks/ol5.md) |
| **MEM-8 / 記憶パイプライン** | [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) · [mem-pipeline.md](./architecture/mem-pipeline.md) |
| **運用スクリプト** | [ops/scripts-reference.md](./ops/scripts-reference.md) |
| **キオスク・Surface 運用** | [ops/](./ops/) · [backlog-koyori.md](./backlog-koyori.md) |
| **LM Studio / KV** | [ops/lmstudio-kv-cache.md](./ops/lmstudio-kv-cache.md) |
| **セッション引き継ぎ** | [handoffs/](./handoffs/) |
| **過去の完了項目** | [backlog-archive-ma-home.md](./backlog-archive-ma-home.md) |

## フォルダ構成

```
docs/
├── README.md                 ← このファイル
├── VISION.md                 プロジェクトの「なぜ」
├── backlog-ma-home.md        ダッシュボード（~150行）
├── backlog-archive-ma-home.md  完了一覧
├── backlog-koyori.md         トピック索引（こより端・記憶・カメラ等）
│
├── tracks/                   トラック仕様（進行中 + 計画済）
│   ├── alive-lw-read.md
│   ├── gw-silent.md
│   ├── ol5.md
│   ├── k-self-code.md
│   ├── vis-health.md
│   ├── obs.md
│   ├── cam-tapo-ptz.md
│   ├── ear.md
│   ├── gapi.md
│   ├── utterance-anchoring.md
│   └── surface-vision.md
│
├── architecture/
│   ├── cognitive-layers.md       設計方針の正
│   ├── platform-ma-home.md       8080・A様子見
│   ├── mem-8-encode-retrieve.md
│   ├── mem-pipeline.md
│   ├── outbound-channels.md
│   ├── gateway-direct-actions.md
│   ├── heartbeat-loop.md
│   ├── intent-bucket-flow.md
│   └── open-loops-reminders.md
│
├── ops/                      運用手順・ハードウェア・LM Studio
│   ├── koyori-input-sharing.md
│   ├── koyori-kiosk-*.md
│   ├── lmstudio-*.md
│   └── ...
│
├── handoffs/                 セッション引き継ぎ（1枚 + Linksee）
├── archive/                  旧バックログ全文・決定記録・セッション export
└── tmp/                      一時ログ（コミットしない想定）
```

---

## tracks/

| ファイル | 内容 |
|----------|------|
| [alive-lw-read.md](./tracks/alive-lw-read.md) | 北極星・LW-READ |
| [gw-silent.md](./tracks/gw-silent.md) | 黙考・OL-GATE |
| [ol5.md](./tracks/ol5.md) | 予定消化 loop close |
| [k-self-code.md](./tracks/k-self-code.md) | 自己コード（将来） |
| [vis-health.md](./tracks/vis-health.md) | VL health・間接視覚 |
| [obs.md](./tracks/obs.md) | `/observe` フェーズ化 |
| [cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md) | Tapo PTZ 調査 |
| [ear.md](./tracks/ear.md) | Surface マイク・環境音 |
| [gapi.md](./tracks/gapi.md) | Google Calendar/Drive |
| [utterance-anchoring.md](./tracks/utterance-anchoring.md) | TEMP · 相対日 / uttered_at |
| [surface-vision.md](./tracks/surface-vision.md) | V1–V9 UI 残件 |

---

## architecture/

| ファイル | 内容 |
|----------|------|
| [cognitive-layers.md](./architecture/cognitive-layers.md) | **設計方針の正** |
| [platform-ma-home.md](./architecture/platform-ma-home.md) | 本線・様子見 |
| [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) | encode/retrieve 非対称 |
| [mem-pipeline.md](./architecture/mem-pipeline.md) | 4層・Dreaming・5e/5f/5k/7 |
| [outbound-channels.md](./architecture/outbound-channels.md) | 能動届け A4 |
| [gateway-direct-actions.md](./architecture/gateway-direct-actions.md) | gateway 直実行 |
| [heartbeat-loop.md](./architecture/heartbeat-loop.md) | pulse・BIO |
| [intent-bucket-flow.md](./architecture/intent-bucket-flow.md) | IBF |
| [open-loops-reminders.md](./architecture/open-loops-reminders.md) | OL・OL-GATE |

---

## ops/ — 運用・ハードウェア

| ファイル | 内容 |
|----------|------|
| [koyori-input-sharing.md](./ops/koyori-input-sharing.md) | Input Leap・KB 共有 |
| [koyori-kiosk-browser.md](./ops/koyori-kiosk-browser.md) | キオスクブラウザ |
| [koyori-kiosk-ime.md](./ops/koyori-kiosk-ime.md) | 日本語 IME |
| [koyori-near-eye.md](./ops/koyori-near-eye.md) | 近眼カメラ |
| [koyori-usb-c-recovery.md](./ops/koyori-usb-c-recovery.md) | USB-C 復旧 |
| [kiosk-primary-say.md](./ops/kiosk-primary-say.md) | キオスク優先発話 |
| [lmstudio-kv-cache.md](./ops/lmstudio-kv-cache.md) | KV cache・Concurrent Predictions |
| [lmstudio-model-change.md](./ops/lmstudio-model-change.md) | モデル変更手順 |
| [role-persistence-ma-home.md](./ops/role-persistence-ma-home.md) | SOUL.core / RP |
| [ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) | 会話 Web 検索 WS-1〜2c |
| [ws-5-spontaneous-search.md](./ops/ws-5-spontaneous-search.md) | 自発検索 WS-5 |
| [scripts-reference.md](./ops/scripts-reference.md) | 運用スクリプト早見 |
| [ma-home-cursor-handoff.md](./ops/ma-home-cursor-handoff.md) | Cursor 引き継ぎ |
| [presence-ui.local.env.example](./ops/presence-ui.local.env.example) | presence-ui 環境変数例 |

---

## archive/ — 参照用（いま触らない）

| ファイル | 内容 |
|----------|------|
| [archive-index.md](./archive/archive-index.md) | 全文アーカイブ索引・漏れチェック |
| [backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md) | 整理前の全バックログ（スナップショット） |
| [c1-native-poc.md](./archive/c1-native-poc.md) | Native PoC 決定 |
| [c2-twicc-decision.md](./archive/c2-twicc-decision.md) | twicc 見送り |
| [mission-A_Investigation-Report.md](./archive/mission-A_Investigation-Report.md) | ミッション A 調査 |
| [web_ui_design.md](./archive/web_ui_design.md) | 旧 Web UI 設計 |
| `cursor-*` / `session-export-*` | 長いセッション export |

---

## handoffs/

短期の作業引き継ぎ。形式は [handoffs/README.md](./handoffs/README.md)。

---

## ステータス記号（backlog 共通）

🔥 進行中 · 📋 次 · 💤 様子見 · ✅ 運用 · 🪦 閉 · 🚫 見送り
