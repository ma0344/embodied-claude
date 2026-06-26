# ma-home / koyori バックログ（ダッシュボード）

**最終更新**: 2026-06-26  
**詳細の正（アーカイブ）**: [archive/backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md)  
**完了一覧**: [backlog-archive-ma-home.md](./backlog-archive-ma-home.md)

---

## 北極星

**こよりがもっと「生きてる」感** — まーと話してない時間にも内側が動き、部屋でさりげなく見える。

第一シーン: **LW-READ**（一冊完走・READ/PAUSE/CLOSE）→ **GW-S1** 黙考 → **LW-7** Web 連鎖。

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

## 次の 3 手

1. **LW-READ v0 様子見** — tick log で `read` / `reflect` が交互か。`~/.claude/aozora_read_state.json` の `phase` を確認。→ [tracks/alive-lw-read.md](./tracks/alive-lw-read.md)
2. **v1 GW-S1 判断** — PAUSE をテンプレから黙考へ配線するか決める。→ [tracks/gw-silent.md](./tracks/gw-silent.md)
3. **K1** — こより自身のコード経路（急がない）。→ [tracks/k-self-code.md](./tracks/k-self-code.md)

反映後: `.\scripts\restart-presence-ui.ps1`

---

## アクティブトラック

| トラック | 内容 | 状態 | 詳細 |
|---------|------|------|------|
| **ALIVE / LW** | 生きてる感・青空読書 | 🔥 v0 運用中 → v1 GW-S1 | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **GW** | 黙考ルート（shared interpret） | 📋 プロンプト済・S1 未配線 | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** | 予定消化で loop close | 📋 GW-S1 依存 | [tracks/ol5.md](./tracks/ol5.md) |
| **K** | こより自身のコード | 💤 方針メモのみ | [tracks/k-self-code.md](./tracks/k-self-code.md) |

---

## 運用中（触らなくてよい）

| トラック | 内容 | 状態 | 参照 |
|---------|------|------|------|
| **A3** | Gateway 直実行（see / observe / tick / 青空） | ✅ | [architecture/gateway-direct-actions.md](./architecture/gateway-direct-actions.md) |
| **BIO** | HeartbeatLoop + pulse | ✅ | [architecture/heartbeat-loop.md](./architecture/heartbeat-loop.md) |
| **BIO-8** | Somatic loop（目・声・memory） | ✅ a–d | アーカイブ § BIO-8 |
| **IBF** | Intent→Bucket→Flow | ✅ | [architecture/intent-bucket-flow.md](./architecture/intent-bucket-flow.md) |
| **OL** | Open loops / リマインド | ✅ 運用確認 | [architecture/open-loops-reminders.md](./architecture/open-loops-reminders.md) |
| **A4** | Outbound（着信・tick・ntfy） | ✅ | アーカイブ § A4 |
| **MEM** | 記憶層・Dreaming | ✅ 5a–5f-c | アーカイブ § MEM |
| **RP** | SOUL.core / stable append | ✅ Phase 0–1 | [ops/role-persistence-ma-home.md](./ops/role-persistence-ma-home.md) |
| **C** | 部屋 UI Native + キオスク | ✅ C11 実戦 OK | アーカイブ § C |
| **B** | Task 常駐・診断 | ✅ B2 除く | 下記 |

---

## 様子見・計画済（急がない）

| トラック | 内容 | 状態 |
|---------|------|------|
| **A** | 記憶・gateway 身体の大追加 | 💤 |
| **OBS** | `/observe` gateway フェーズ化 | 📋 |
| **CAM** | Tapo PTZ / ONVIF 細かい操作 | 💤 |
| **EAR** | Surface マイク → social | 📋 |
| **GAPI** | Google Calendar / Drive | 📋 |
| **VIS** | VL corrupt 相関ログ | 💤 |
| **V** | Surface ビジョン（V4 see_near 等） | 💤 V5 済 |
| **WS** | 会話 Web 検索 | ✅ WS-1〜2c | [ops/ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) |

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
| Gateway `:8090` | compose/plan + 身体直実行 + LW-READ v0 |
| UI | Native 本線 + キオスク（`?kiosk=1`） |
| TTS | Aivis るな + `voice_local` |
| Outbound | 着信・15m tick・ntfy |

設備マニュアル: [CLAUDE.md](../CLAUDE.md)  
なぜ・何を目指すか: [VISION.md](./VISION.md)

---

## ドキュメントの読み方

→ [README.md](./README.md)
