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
| **キオスク・Surface 運用** | [ops/](./ops/) 配下（下表） |
| **LM Studio / KV** | [ops/lmstudio-kv-cache.md](./ops/lmstudio-kv-cache.md) |
| **セッション引き継ぎ** | [handoffs/](./handoffs/) |
| **過去の完了項目** | [backlog-archive-ma-home.md](./backlog-archive-ma-home.md) |
| **2026-06 以前の詳細仕様** | [archive/backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md) |

---

## フォルダ構成

```
docs/
├── README.md                 ← このファイル
├── VISION.md                 プロジェクトの「なぜ」
├── backlog-ma-home.md        ダッシュボード（~150行）
├── backlog-archive-ma-home.md  完了一覧
├── backlog-koyori.md         トピック索引（こより端・記憶・カメラ等）
│
├── tracks/                   🔥 進行中トラックの仕様
│   ├── alive-lw-read.md
│   ├── gw-silent.md
│   ├── ol5.md
│   └── k-self-code.md
│
├── architecture/             本体の設計（Gateway・Heartbeat・OL）
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

## tracks/ — 進行中

| ファイル | 内容 |
|----------|------|
| [alive-lw-read.md](./tracks/alive-lw-read.md) | 北極星・LW-READ v0/v1・運用チェック |
| [gw-silent.md](./tracks/gw-silent.md) | 黙考ルート・GW-S1 配線判断 |
| [ol5.md](./tracks/ol5.md) | 予定消化で loop close |
| [k-self-code.md](./tracks/k-self-code.md) | こより自身のコード（将来） |

---

## architecture/ — 本体設計

| ファイル | 内容 |
|----------|------|
| [gateway-direct-actions.md](./architecture/gateway-direct-actions.md) | see / observe / tick / 青空の直実行 |
| [heartbeat-loop.md](./architecture/heartbeat-loop.md) | pulse・経験→次の wake |
| [intent-bucket-flow.md](./architecture/intent-bucket-flow.md) | 会話の Intent→Bucket→Flow |
| [open-loops-reminders.md](./architecture/open-loops-reminders.md) | OL1/OL2 リマインド運用 |

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
| [ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) | 会話 Web 検索 |
| [ma-home-cursor-handoff.md](./ops/ma-home-cursor-handoff.md) | Cursor 引き継ぎ |
| [presence-ui.local.env.example](./ops/presence-ui.local.env.example) | presence-ui 環境変数例 |

---

## archive/ — 参照用（いま触らない）

| ファイル | 内容 |
|----------|------|
| [backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md) | 整理前の全バックログ |
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
