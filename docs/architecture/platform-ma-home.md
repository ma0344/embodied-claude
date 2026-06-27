# ma-home プラットフォーム方針（合意）

**関連**: [backlog-ma-home.md](../backlog-ma-home.md)、[cognitive-layers.md](./cognitive-layers.md)

---

## 会話本線

| 項目 | 決定 |
|------|------|
| 会話エンジン | Native — `claude-code-server` → `/api/native/chat` |
| 本番 URL | `http://localhost:8090/`（presence-ui） |
| 8080 webui | **任意**。新機能は載せない。Task 外してよい（C9 済） |
| キオスク | Surface → ma-home `:8090/?kiosk=1`（8080 直結ではない） |

**やらない**: 8080 前提の UI 投資（project/history プロキシ、8080 セッション削除 UI 等）。

---

## 開発投資の様子見（A トラック）

**合意**: 記憶・gateway への **大きな追加は止める**（2026-06 整理時）。

| やる | やらない（当面） |
|------|------------------|
| 縦スライス（LW/GW/OL-GATE） | 記憶アーキテクチャの全面再設計 |
| gateway 直実行の穴埋め | MCP ツール JSON を増やす |
| MEM-8 の段階的パッチ（8a/8d 等） | Dreaming 以外の新 LTM チャネル乱立 |

例外: バグ修正、運用必須（OL-GATE、prefetch）、BIO/GW ループを閉じる配線。

---

## LM Studio

| 項目 | 決定 |
|------|------|
| B2 自動ロード | 🪦 閉 — 手動 + `check-koyori-stack.ps1` 警告 |
| Concurrent Predictions | **1**（KV） |
| 二モデル | Gemma 会話 + Qwen vision（KV 分離） |

---

## 優先の北極星

**生きてる感** > 機能の正しさ（OL/IBF 単体）。第一シーン: LW-READ → GW-S1 → LW-7。

K（自己コード）は **GW + BIO ループが閉じてから** → [k-self-code.md](../tracks/k-self-code.md)。

全文コンテキスト: [archive 先頭](../archive/backlog-ma-home-full-2026-06-26.md)
