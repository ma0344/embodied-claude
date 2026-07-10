# ma-home / koyori バックログ（ダッシュボード）

**最終更新**: 2026-07-01（GAPI-2 読取パイプライン ma-home E2E）  
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
| **★** | **ALIVE / LW** | 生きてる感の第一シーン（青空読書） | 🔥 LW-7 運用確認 |
| **1** | **BIO** | Heartbeat ループ骨格（pulse・somatic・tick） | ✅ 基盤済 — interpret 一部閉（PAUSE） |
| **2** | **GW** | 黙考ルート（shared interpret） | ✅ S1 · ✅ S2 · ✅ Claude resume（opt-in） |
| **3** | **OL5** | 予定消化で loop close | ✅ a/b/c/6/STALE/d · 📋 **OL7** |
| **—** | **K** | こより自身のコード | 💤 **GW + BIO ループが閉じてから** |

---

## 次の 3 手

1. **（運用確認）LW-7** — `PRESENCE_LW7_ENABLED=1`（example 既定 ON · 実機で PAUSE→Web）→ [tracks/alive-lw-read.md](./tracks/alive-lw-read.md)

（完了）**SHIFT-R3** — `interpretation_shifts.domain` + inject filter → [interpretation-shift-routing.md](./tracks/interpretation-shift-routing.md)

デプロイ: `cd presence-ui` → `uv pip install --reinstall "relationship-mcp @ file:///…/relationship-mcp"` → `.\scripts\restart-presence-ui.ps1`

---

## アクティブトラック

| トラック | 内容 | 状態 | 詳細 |
|---------|------|------|------|
| **ALIVE / LW** | 生きてる感・青空読書 | 🔥 LW-7 ON（運用確認） | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **BIO** | ループ骨格（pulse・somatic・経験→wake） | ✅ 基盤済 · PAUSE interpret 閉 | [architecture/heartbeat-loop.md](./architecture/heartbeat-loop.md) |
| **GW** | 黙考ルート（**interpret** 層） | ✅ S1 · ✅ S2 · ✅ resume（opt-in） | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** | 予定消化 loop close | ✅ a/b/c/6/STALE/d · 📋 OL7 return-signal | [tracks/ol5.md](./tracks/ol5.md) |
| **MEM-8g** | compose salience · 終了スレの繰り返し抑制 | 💤 v0 運用確認 · 📋 **v1 gist 本線** | [tracks/compose-topic-retire.md](./tracks/compose-topic-retire.md) |
| **MEM-8h** | memory bridge · Surface compact transcript | ✅ **A–D** | [tracks/mem-8h-memory-bridge.md](./tracks/mem-8h-memory-bridge.md) · [surface-direct-llm.md](./tracks/surface-direct-llm.md) |

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
| **OBS-TICK** | tick 視覚 encode（MEM-8 系） | 🔥 **0 実験** · 📋 **1 草案** | [tracks/obs-tick-encode.md](./tracks/obs-tick-encode.md) |
| **CAM** | Tapo PTZ | 💤 | [tracks/cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md) |
| **EAR** | Surface マイク | 📋 | [tracks/ear.md](./tracks/ear.md) |
| **VIS** | VL health · vision **12b-qat** | ✅ 切替済（2026-07-06） | [vis-health.md](./tracks/vis-health.md) |
| **V** | Surface UI 残（V4 等） | 部分済 | [tracks/surface-vision.md](./tracks/surface-vision.md) |
| **GAPI** | Google Calendar / Drive | ✅ prep-1/2/3 · 7a/7b · **2b/2r/2r-S2/2s** · 📋 **7c** 複数件 · **7d** e4b確認 | [tracks/gapi.md](./tracks/gapi.md) · [gapi-setup.md](./ops/gapi-setup.md) |
| **TEMP** | TEMP-1〜5 ✅ · TEMP-C3/b/c4 ✅ · **C5 📋** clock/e4b · SHIFT-R1/R2/R3 ✅ | [utterance-anchoring.md](./tracks/utterance-anchoring.md) · [interpretation-shift-routing.md](./tracks/interpretation-shift-routing.md) |
| **WS** | 会話 Web 検索 | ✅ WS-5 v0 · 📋 v1 e4b | [ws-2](./ops/ws-2-conversation-web-search.md) · [ws-5](./ops/ws-5-spontaneous-search.md) |

トピック索引: [backlog-koyori.md](./backlog-koyori.md)

---

## 運用自動化（B）

**やりたいこと**: ログオン後、手で起動せず本体が使える状態にする。

| サービス | Task | スクリプト |
|---------|------|-----------|
| memory HTTP | `EmbodiedClaude-MemoryHTTP` | `install-memory-daemon-task.ps1` |
| Irodori TTS | `EmbodiedClaude-IrodoriTTS` | `install-irodori-tts-task.ps1` |
| AivisSpeech（フォールバック） | `EmbodiedClaude-AivisTTS` | `install-aivis-tts-task.ps1`（併存非推奨） |
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
| TTS | Irodori `:8088` + `voice_local`（Aivis はフォールバック） |
| Outbound | 着信・15m tick・ntfy |

### Irodori TTS カットオーバー（必須）

**presence-ui は `mcpBehavior.toml` を読まない。** 実機の正本は `tts-mcp/.env` の `TTS_DEFAULT_ENGINE` / `IRODORI_*`（`.env.example` 準拠）。TOML の `default_engine` だけでは surface / `speak_text` は切り替わらない。

```powershell
# 1. tts-mcp/.env を .env.example 準拠に（IRODORI_* + TTS_DEFAULT_ENGINE=irodori）
# 2. presence-ui の path dep を再インストール
cd presence-ui; uv sync --reinstall-package tts-mcp
#    または: .\scripts\sync-presence-deps.ps1
# 3. Task 切替（併存非推奨）
.\scripts\install-irodori-tts-task.ps1
.\scripts\install-aivis-tts-task.ps1 -Uninstall   # または Disable-ScheduledTask EmbodiedClaude-AivisTTS
Start-ScheduledTask -TaskName EmbodiedClaude-IrodoriTTS
# 4. presence-ui 再起動
.\scripts\restart-presence-ui.ps1
# 5. 確認
curl -s http://127.0.0.1:8088/health
curl -s http://127.0.0.1:8090/api/v1/health
# 短い発話（キオスク or miss_companion smoke）
```

### Irodori 参照声 WAV の差し替え

voice 名 **`koyori`** = `Irodori-TTS-Server/voices/koyori.wav`（拡張子除いたファイル名が `IRODORI_VOICE`）。

```powershell
# 1. 新しい参照 wav を voices に上書き（パスは任意のソースで可）
$Voices = "$env:USERPROFILE\src\Irodori-TTS-Server\voices"   # 既定 clone 先
Copy-Item "C:\Users\ma\Desktop\rec_03.wav" (Join-Path $Voices "koyori.wav") -Force

# 2. Irodori 再起動（voice 一覧は起動時に読む）
$p = (Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($p) { Stop-Process -Id $p -Force }
cd C:\Users\ma\src\embodied-claude
.\scripts\start-irodori-tts.ps1 -Background

# 3. surface TTS キャッシュ削除（wav 差し替え前の合成が残ると古い声が流れる）
Remove-Item "$env:LOCALAPPDATA\Temp\wifi-cam-mcp\tts-surface\*" -Force -ErrorAction SilentlyContinue
#    CAPTURE_DIR を使っている場合は %CAPTURE_DIR%\tts-surface\ も同様

# 4. 確認
curl -s http://127.0.0.1:8088/health   # voices.files >= 1
# キオスク or 短い発話で聴く
```

**env（変更不要ならスキップ）**: `tts-mcp/.env` と `presence-ui.local.env` の `IRODORI_VOICE=koyori` / `IRODORI_SEED` / `IRODORI_CFG_SCALE_*` は [tts-mcp/.env.example](../../tts-mcp/.env.example) 参照。voice 名を変えるときだけ `IRODORI_VOICE` を新ファイル名に合わせる。

**別名で追加したい場合**: `voices/別名.wav` を置き `IRODORI_VOICE=別名` に変更 → Irodori 再起動 + キャッシュ削除 + `restart-presence-ui.ps1`（env 変更時）。

設備マニュアル: [CLAUDE.md](../CLAUDE.md)  
設計・索引: [cognitive-layers.md](./architecture/cognitive-layers.md) · [archive-index.md](./archive/archive-index.md)  
なぜ: [VISION.md](./VISION.md)

---

## ドキュメントの読み方

→ [README.md](./README.md)
