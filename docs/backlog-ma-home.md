# ma-home / koyori バックログ（ダッシュボード）

**最終更新**: 2026-06-29（OL5-c ✅ · TEMP-C4 ✅ · 朝挨拶=幽霊禁止のみ）  
**詳細の正（アーカイブ）**: [archive/backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md)  
**完了一覧**: [backlog-archive-ma-home.md](./backlog-archive-ma-home.md)

---

## 北極星

**こよりがもっと「生きてる」感** — まーと話してない時間にも内側が動き、部屋でさりげなく見える。

第一シーン: **LW-READ**（一冊完走・READ/PAUSE/CLOSE）→ **GW-S1** 黙考 → **LW-7** Web 連鎖。

**骨格（合意 2026-06-26）**: LW・**BIO**・将来の K は同じループ — `notice → interpret → choose → act → remember → schedule`。**interpret = GW-SILENT**。インフラ（pulse・somatic・tick）は **BIO 済**；**GW-S1 は tick PAUSE に配線済**（2026-06-25）。

**設計方針（合意 2026-06-26）**: 新機能・LLM 追加の前に [cognitive-layers.md](./architecture/cognitive-layers.md)（表層 / 前頭葉 / 実装前 3 問）。記憶は [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md)。全文アーカイブの漏れチェック → [archive/archive-index.md](./archive/archive-index.md)。

---

## ステータス凡例

| 記号 | 意味 |
|------|------|
| 🔥 | 進行中（いま触る） |
| 📋 | 次（直近の候補） |
| 💤 | 様子見（運用しながら様子を見る） |
| ✅ | 運用中（実装済み・維持） |
| 🪦 | 閉（現状で終了・追加実装しない） |
| 🚫 | 見送り |

---

## 優先順（骨格）

| 順 | トラック | 内容 | 状態 |
|----|---------|------|------|
| **★** | **ALIVE / LW** | 生きてる感の第一シーン（青空読書） | 🔥 v1 GW-S1 運用 → **LW-7** |
| **1** | **BIO** | Heartbeat ループ骨格（pulse・somatic・tick） | ✅ 基盤済 — interpret 一部閉（PAUSE） |
| **2** | **GW** | 黙考ルート（shared interpret） | ✅ S1 · ✅ S2（`PRESENCE_GW_S2_ENABLED=1`）· 📋 Claude resume |
| **3** | **OL5** | 予定消化で loop close | ✅ a/b/c/6 · 📋 OL-STALE |
| **—** | **K** | こより自身のコード | 💤 **GW + BIO ループが閉じてから** |

---

## 次の 3 手

1. **OL-STALE** — 日跨ぎ exempt → [ol5.md](./tracks/ol5.md) · [open-loops-reminders.md](./architecture/open-loops-reminders.md#ol-stale--日跨ぎで閉じない-loop)
2. **TEMP-5** — dream_digest / memories anchor（幽霊除去 · inject 側）

（並行）**LW-7** — `PRESENCE_LW7_ENABLED=1` → [tracks/alive-lw-read.md](./tracks/alive-lw-read.md)

デプロイ: `cd presence-ui` → `uv pip install --reinstall "relationship-mcp @ file:///…/relationship-mcp"` → `.\scripts\restart-presence-ui.ps1`

---

## アクティブトラック

| トラック | 内容 | 状態 | 詳細 |
|---------|------|------|------|
| **ALIVE / LW** | 生きてる感・青空読書 | 🔥 LW-7 下準備済 | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **BIO** | ループ骨格（pulse・somatic・経験→wake） | ✅ 基盤済 · PAUSE interpret 閉 | [architecture/heartbeat-loop.md](./architecture/heartbeat-loop.md) |
| **GW** | 黙考ルート（**interpret** 層） | ✅ S1 · ✅ S2（opt-in）· 📋 resume | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** | 予定消化 loop close · **OL-STALE** | ✅ a/b/c/6 · 📋 STALE | [tracks/ol5.md](./tracks/ol5.md) |

---

## 運用中（触らなくてよい）

| トラック | 内容 | 状態 | 参照 |
|---------|------|------|------|
| **A3** | Gateway 直実行（see / observe / tick / 青空） | ✅ | [architecture/gateway-direct-actions.md](./architecture/gateway-direct-actions.md) |
| **BIO-8** | Somatic loop（目・声・memory） | ✅ a–d | [heartbeat-loop.md](./architecture/heartbeat-loop.md) · [vis-health.md](./tracks/vis-health.md) |
| **IBF** | Intent→Bucket→Flow | ✅ | [architecture/intent-bucket-flow.md](./architecture/intent-bucket-flow.md) |
| **OL** | Open loops / リマインド | ✅ 運用 · ✅ OL-GATE（GW-S2 opt-in）· ✅ `list_open_loops.detail` | [architecture/open-loops-reminders.md](./architecture/open-loops-reminders.md) |
| **A4** | Outbound（着信・tick・ntfy） | ✅ | [outbound-channels.md](./architecture/outbound-channels.md) |
| **MEM** | 記憶層・Dreaming | ✅ 5a–5f-c · 📋 MEM-8 概念 | [mem-pipeline.md](./architecture/mem-pipeline.md) · [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) |
| **RP** | SOUL.core / stable append | ✅ Phase 0–1 | [ops/role-persistence-ma-home.md](./ops/role-persistence-ma-home.md) |
| **C** | 部屋 UI Native + キオスク | ✅ C11 実戦 OK | [surface-vision.md](./tracks/surface-vision.md) · [platform-ma-home.md](./architecture/platform-ma-home.md) |
| **B** | Task 常駐・診断 | ✅ B2 除く | [scripts-reference.md](./ops/scripts-reference.md) |

---

## 様子見・計画済（急がない）

**注（アーカイブ合意）**: 記憶・gateway への **大きな追加は様子見**（A トラック）。縦スライス（LW/GW/OL-GATE）以外の MEM 拡張は [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) の優先案を参照。

| トラック | 内容 | 状態 |
|---------|------|------|
| **K** | こより自身のコード | 💤 | [tracks/k-self-code.md](./tracks/k-self-code.md) |
| **A** | 記憶・gateway 大追加 | 💤 | [platform-ma-home.md](./architecture/platform-ma-home.md) |
| **OBS** | `/observe` フェーズ化 | 📋 | [tracks/obs.md](./tracks/obs.md) |
| **CAM** | Tapo PTZ | 💤 | [tracks/cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md) |
| **EAR** | Surface マイク | 📋 | [tracks/ear.md](./tracks/ear.md) |
| **VIS** | VL health · **Qwen→e4b vision POC**（事前テスト必須） | 💤 POC 待ち | [tracks/vis-health.md](./tracks/vis-health.md) |
| **V** | Surface UI 残（V4 等） | 部分済 | [tracks/surface-vision.md](./tracks/surface-vision.md) |
| **GAPI** | Google Calendar / Drive | ✅ prep-1/2 CLI · 📋 配線要検討 → prep-3 | [tracks/gapi.md](./tracks/gapi.md) · [gapi-setup.md](./ops/gapi-setup.md) |
| **TEMP** | TEMP-1〜4/b ✅ · TEMP-C3/b/c4 ✅ · SHIFT-R1/R2 ✅ · **TEMP-5 📋** | [utterance-anchoring.md](./tracks/utterance-anchoring.md) · [interpretation-shift-routing.md](./tracks/interpretation-shift-routing.md) |
| **WS** | 会話 Web 検索 | ✅ WS-1〜2c · 📋 WS-5（[北極星: 地震例](./ops/ws-5-spontaneous-search.md#北極星シナリオ--会話中の興味疑問2026-06-27)） | [ws-2](./ops/ws-2-conversation-web-search.md) · [ws-5](./ops/ws-5-spontaneous-search.md) |

トピック索引: [backlog-koyori.md](./backlog-koyori.md)

---

## 運用自動化（B）

**やりたいこと**: ログオン後、手で起動せず本体が使える状態にする。

| サービス | Task | スクリプト |
|---------|------|-----------|
| memory HTTP | `EmbodiedClaude-MemoryHTTP` | `install-memory-daemon-task.ps1` |
| AivisSpeech | `EmbodiedClaude-AivisTTS` | `install-aivis-tts-task.ps1` |
| presence-ui | `EmbodiedClaude-PresenceUI` | `install-presence-ui-task.ps1` |
| Watchdog | `EmbodiedClaude-Watchdog` | `install-embodied-watchdog-task.ps1` |

**診断**:

```powershell
.\scripts\check-koyori-stack.ps1    # LM Studio 手動ロードの警告含む
.\scripts\post-logon-smoke.ps1
.\scripts\verify-mission-a.ps1
```

| ID | 内容 | 状態 |
|----|------|------|
| B1 | Scheduled Task 登録 | ✅ |
| B3 | Watchdog | ✅ |
| B4 | ターミナル非表示（hidden launcher） | ✅ 2026-06-26 |
| **B2** | LM Studio 自動ロード | **🪦 閉** — 手動ロード + `check-koyori-stack.ps1` 警告で十分（2026-06-26 合意） |

---

## いまのスタック（要約）

| 層 | 状態 |
|----|------|
| 記憶 | HTTP `:18900` 常駐。compose / gateway remember OK |
| Gateway `:8090` | compose/plan + 身体直実行 + LW-READ v1（GW-S1 PAUSE）+ OL-GATE ingest（GW-S2 opt-in） |
| **BIO** | pulse + somatic + tick — PAUSE で interpret 一部稼働 |
| UI | Native 本線 + キオスク（`?kiosk=1`） |
| TTS | Aivis るな + `voice_local` |
| Outbound | 着信・15m tick・ntfy |

設備マニュアル: [CLAUDE.md](../CLAUDE.md)  
設計・索引: [cognitive-layers.md](./architecture/cognitive-layers.md) · [archive-index.md](./archive/archive-index.md)  
なぜ: [VISION.md](./VISION.md)

---

## ドキュメントの読み方

→ [README.md](./README.md)
