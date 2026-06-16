# ma-home / koyori バックログ

**最終更新**: 2026-06-10（優先 1→3→2→C11g 合意 + V ビジョン追記）  
**方針**: こより本体（記憶・gateway 身体）は **様子見**。部屋 UI は **Native 会話エンジン + `/` の殻** を育てる（8080 プロキシ UI は投資しない）。

**実行方針（合意 2026-06-14）**: 判断は compose/plan/stores のまま。**身体・自律の実行**は MCP に頼らず gateway 直実行へ（remember 直実行と同型）。詳細 → [gateway-direct-actions.md](./gateway-direct-actions.md)

あとでやること。完了したら `[x]` にするか「完了」セクションへ移す。

---

## 優先順（合意 2026-06-13 → **2026-06-15 更新**）

| 順 | トラック | 内容 | 状態 |
|----|---------|------|------|
| **D** | Backlog 最新化 | このファイルを現実に合わせる | **随時** |
| **B** | 運用自動化 | ログオン常駐・手起動を減らす | **ほぼ完了**（B2 LM Studio 手動のみ） |
| **C** | **部屋 UI（Native + Surface）** | `/` 殻 + キオスク UX | **C11 実戦 OK** → 磨きは任意 |
| **A4** | **能動届け（Outbound）** | A4b+/c+/f/g 実装済み | **OL2** |
| **OL** | Open Loops / リマインド | 日付解決 + commitment + 発火 | A4b/f とセット |
| **A** | 記憶・gateway 身体 | compose / see / dismiss | **様子見**（大きな追加は止める） |
| **C12** | intent router | 曖昧な「見て」分類 | 会話快適化（後） |

### 次の一手 — 優先度案（2026-06-10 → **まー合意: 1→3→2→C11g**）

**いまのボトルネック**: 自律 tick（A4f）と Open Loops（OL1/OL2）の配線。PC Push（A4g）はキオスク本線ができたあとでよい。

| tier | 順 | 項目 | 理由 |
|------|----|------|------|
| **1** | ① | **A4f 運用** | `install-autonomous-tick-task.ps1` 登録（15m + desire-updater）— 自律の心臓 |
| **2** | ② | **OL1 + OL2** | 日付解決 + commitment → tick でリマインド |
| **3** | ③ | **A4g 運用** | `PRESENCE_OUTBOUND_NTFY_URL`（外出時・8090 閉じてる PC 向け） |
| **4** | ④ | **C11g** スリープ / 画面消灯 | Surface 常時点灯・焼き付き対策 |
| **—** | ⑤ | **A4j+** / **C12** | 着信返信 UX・intent router（任意） |
| **—** | — | C11c/d、体温 LHM、Irodori TTS | 任意の磨き |

**やらない順**: C12 だけ先にやっても「自律で話しかけてこない」は **A4f** 待ち。

**フェーズ判断（2026-06-10）**: A4a/e/i + `voice_local`（Aivis **るな**）は **運用中**。**A4c+** で部屋着信は Server TTS（Web Speech はフォールバックのみ）。

**UI と本体の兼ね合い**: ミッションA の「人間1ターン」は **CLI でも `:8090/` でも可**。本体変更時は `restart-presence-ui.ps1`（内部で `sync-presence-deps`）。

---

## 今どこにいるか（2026-06-10）

| 層 | 状態 |
|----|------|
| **記憶インフラ** | HTTP daemon `:18900` 常駐。compose recall・gateway remember **OK** |
| **Gateway `:8090`** | compose/plan + KV 安定注入。**身体は gateway 直実行済み**（see / observe / reflect / autonomous-tick）。vision prefetch + remember **実戦 OK** |
| **関係性** | open loop dismiss + commitment cancel。「覚えてる？」recall 誤 loop 抑制 |
| **表面 UI** | **Native 本線** + キオスク着信（A4i）。**A4j** 着信返信は native chat 自動送信 |
| **TTS（ma-home）** | **AivisSpeech** `:10101`（`scripts/start-aivis-tts.ps1`）。声 **るな**（style `345585728`）。`voice_local` 運用中。Irodori は参照声待ちで保留 |
| **Outbound** | A4i/j + **A4f**（15m tick Task）+ **A4g**（enqueue → ntfy/Pushover）。PC `voice_local` |
| **運用** | Task×3〜4（memory / presence / watchdog。**webui 任意**）+ post-logon-smoke **Native 対応** |

参照: [gateway-direct-actions.md](./gateway-direct-actions.md)、[mission-A_Investigation-Report.md](./mission-A_Investigation-Report.md)

---

## 完了（2026-06 〜 2026-06-13）

- [x] **HttpMemoryAdapter** — compose が `:18900` → SQLite フォールバック（`ORCHESTRATOR_MEMORY_BACKEND=auto`）
- [x] **キオスク記憶 UX（A+B）** — Gateway が「覚えておいて」→ `POST :18900/remember`。`room_progress` / `room_activity` 表示
- [x] **キオスク書き込み権限** — `permissionMode: acceptEdits`（`social_chat.py` / `app.js`）
- [x] **長セッション二重注入** — `claude_session_resume` で arc サマリのみ
- [x] **memory ハング緩和** — stdio→HTTP 委譲（`MEMORY_STDIO_DELEGATE_HTTP`）、`MEMORY_MCP_TOOL_TIMEOUT_SEC=45`、`check-mcp-processes.ps1` STALE 表示
- [x] **hook タイムアウト** — UserPromptSubmit 5s→30s（E5 warm-up + remember で `[memory_saved_server]` が落ちる問題）
- [x] **8090 KV 安定化** — 可変 compose/plan を user 側へ（`PRESENCE_KV_STABLE_APPEND`）。`f_keep ≈ 0.999` 確認
- [x] **CLI 記憶想起（人間）** — 新セッションで `list_recent` 相当の内容（中標津・煎餅・役割分担等）を返答
- [x] **Backlog 整理 + スモーク脚本** — `test-memory-stack.ps1`（D トラック）
- [x] **A3 gateway 身体（実装）** — see / observe / reflect / autonomous-tick / vision prefetch（2026-06-14）
- [x] **A3 実戦確認（まー）** — 見える・窓/デスク/ダイニング preset・`remember=ok`・煎餅 dismiss（2026-06-14）
- [x] **関係性 dismiss** — 「忘れて/中止」→ open loop close + commitment cancel（2026-06-14）
- [x] **UI snapshot** — ポーリング用キャプチャはディスク保存しない（2026-06-14）

---

## B — 運用自動化（次にやる）

**やりたいこと**: ログオン後、手で起動せず本体が使える状態にする。

| サービス | ポート | Scheduled Task | スクリプト | ログ |
|---------|--------|----------------|-----------|------|
| memory HTTP daemon | 18900 | `EmbodiedClaude-MemoryHTTP` | `install-memory-daemon-task.ps1` | `%USERPROFILE%\.config\embodied-claude\logs\memory-daemon.log` |
| Claude Code Web UI | 8080 | `EmbodiedClaude-WebUI` | `install-webui-task.ps1` | `...\webui.log` | **任意**（Native 本線では不要） |
| presence-ui | 8090 | `EmbodiedClaude-PresenceUI` | `install-presence-ui-task.ps1` | `...\presence-ui.log` |

**推奨登録順**（memory → presence-ui。**8080 webui Task は任意**）:

```powershell
cd C:\Users\ma\src\embodied-claude

.\scripts\install-memory-daemon-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-MemoryHTTP

# 任意 — Native 会話だけなら省略可
# .\scripts\install-webui-task.ps1
# Start-ScheduledTask -TaskName EmbodiedClaude-WebUI

.\scripts\install-presence-ui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-PresenceUI
```

**8080 を外す**（Native 本線確定後）:

```powershell
.\scripts\stop-webui-ma-home.ps1
.\scripts\install-webui-task.ps1 -Uninstall
.\scripts\post-logon-smoke.ps1   # :8080 なしで PASS するはず
```

**再起動後チェック**（`post-logon-smoke.ps1` 一発）:

```powershell
.\scripts\post-logon-smoke.ps1
```

- [x] **B1b** 再起動後 `post-logon-smoke.ps1` — Native 時 :8080 optional（2026-06-10 C9）

**Watchdog（A2b+）** — 2分ごと。stdio kill **5分**（Task 常設）:

```powershell
.\scripts\install-embodied-watchdog-task.ps1   # 既定 StdioHangMinutes=5
Start-ScheduledTask -TaskName EmbodiedClaude-Watchdog
# ログ: %USERPROFILE%\.config\embodied-claude\logs\watchdog.log
```

- [x] **B1** Scheduled Task 3つ登録（`EmbodiedClaude-MemoryHTTP` / `WebUI` / `PresenceUI`）— 2026-06-13 実施
- [x] **B3** Watchdog Task 登録（`EmbodiedClaude-Watchdog`）— 2026-06-14 実施
- [ ] **B2** LM Studio ロードは別途（現状手動 or 既存習慣）
- [ ] **B4** ログオン時ターミナル非表示（VBS ランチャー×3）— **後回し可**。Watchdog 済み。daemon 障害はログ + smoke で検知

**メモ**: Claude Code の stdio MCP（memory/sociality 等）は **セッションごとに spawn** される。daemon は **HTTP 記憶の本店** だけ常駐。診断: `check-mcp-processes.ps1`。

---

## A — 記憶・魂（**様子見** — 大きな追加は止める）

日常で使いながら spot check。月1回程度 `verify-mission-a.ps1` でよい。

### 自動スモーク（手作業削減）

```powershell
# 一発確認（推奨）
.\scripts\verify-mission-a.ps1

# 内訳だけ
.\scripts\test-memory-stack.ps1 -RequireSociality
.\scripts\verify-mission-a.ps1 -SkipGatewayChat   # :8090 chat 省略
```

| 脚 | 脚本 | 人間 |
|----|------|------|
| HTTP remember → recall | `verify-mission-a.ps1` step 1–2 | — |
| compose `relevant_memories` | 同上 | — |
| :8090 会話で煎餅等 | `verify-mission-a.ps1` step 3 | まー確認済み 2026-06-14 |
| CLI 会話 | — | **記憶質問でハング報告あり**（下記） |

- [x] **A1 自動スモーク green** — `verify-mission-a.ps1` / `-RequireSociality` PASS（2026-06-14）
- [x] **A2 人間 E2E（:8090）** — 「煎餅」言い換えで想起 OK（まー確認 2026-06-14）
- [ ] **A2b CLI 記憶質問の安定化** — **観察モード**。**段1 適用済み（2026-06-14）**: daily `enabledMcpjsonServers` = `system-temperature` のみ。**手動プロファイル切替は移行期のみ**（本線は A3 gateway 直実行）。
- [x] **A2b+ ハング検出→再起動** — `watch-embodied-health.ps1` + Task `EmbodiedClaude-Watchdog`（2分間隔）

### A3 — Gateway 直実行（身体・自律）

判断機構は orchestrator のまま。LLM ctx の MCP 削減と desire 本格運用のため、plan → gateway 実行へ。→ [gateway-direct-actions.md](./gateway-direct-actions.md)

- [x] **A3a** `write_private_reflection` — orchestrator 直書き
- [x] **A3b** `observe_room` — boundary → see + observation remember
- [x] **A3c** `miss_companion` — boundary → tts say（`services/tts.py`）
- [x] **A3d** 自律 tick `POST /api/v1/autonomous-tick` + `satisfy_desire` サーバー側
- [x] **A3e** スモーク — observe_room PASS（2026-06-14）
- [x] **A3f/g** vision prefetch（会話 A）+ desire see caption（B）+ 窓/デスク/ダイニング preset
- [x] **A3 実戦** — 窓景色 recall（vision_prefetch + VISION_CAPTION 返答）、会議 open loop、desire 注入確認（2026-06-14）
- [x] **A3h** open loop dismiss + commitment cancel + recall 誤 loop 抑制（2026-06-14）
- [x] **A3c 運用** — `miss_companion` / tick → **Aivis るな** + `voice_local`（`tts-mcp/.env` + `mcpBehavior.toml` + `scripts/start-aivis-tts.ps1`）。Irodori はベンチ済み・参照声待ちで保留
- [ ] **保存と想起の一貫性** — 窓・会議は spot check PASS 済み。「さっき見た」だけ memory 想起（再撮影なし）は任意改善
- [ ] **save_visual_memory HTTP** — MCP 完全 parity。急がない
- [ ] **Gemma `remember` 信頼性** — 観察のみ
- [ ] **初回 remember の遅さ** — 低優先（daemon 常駐で大部分解消）
- [x] **ミッションB/C**（欲求・体験・関係性）— compose `compact_prompt_block` に `[desires]` / `[open_loops]` / `[interpretation_shifts]` / `[recent_experiences]` 注入。plan は shift 本文を `must_include` に載せる（2026-06-14）

### A4 — こよりからの能動届け（Outbound）

**問題（2026-06-15）**: `agent_experiences` は監査ログ。`agent_voice_utterance` 等は「話しかけようとした」記録だが、**まーが見ている端末に届く保証がない**。現状 `talk_to_companion` → `speak_text(local)` は **ma-home PC スピーカーのみ**。Surface キオスクのチャット UI には bubble が出ない。experience だけ増えて「隣にいる」感が成立しない。

**方針**: 判断（compose/plan/boundary）は既存のまま。**実行後に OutboundChannel を明示**し、`channel` + `delivered` を experience に残す。quiet hours / should_interrupt / nudge クールダウンはチャネル単位。

| チャネル | 出力先 | 状態 |
|----------|--------|------|
| `room_inbound` | キオスク中央ダイアログ（poll → 目標 SSE） | **実装済み（A4i）** |
| `chat_compose` | 着信「返事する」→ 新規 native 会話 + 送信 | **実装済み（A4j）** |
| `voice_local` | ma-home PC スピーカー（Aivis via `services/tts.py`） | **運用中** |
| `voice_surface` | Surface スピーカー（**A4c+** Server TTS URL） | **済** — kiosk 優先時は PC ブラウザ無音 |
| `voice_camera` | Tapo / go2rtc カメラ側スピーカー | 設定時のみ |
| `kiosk_banner` | Surface 部屋 UI ヘッダー／トースト（視覚のみ） | 未実装 |
| `push_windows` / `push_android` | ntfy / Pushover 等（**A4g**） | **実装済み**（env 要） |
| `silent` | private reflection のみ（届けない） | 実装済み |

**外部 Push サービス（検討）**: 自前 FCM/APNs より、**他との関係を閉じた専用アカウント**で API 叩けるものを優先検討。

- **ntfy** — 自ホスト or ntfy.sh 専用 topic、Android/iOS/Web クライアント
- **Pushover** / **Gotify** — 個人向け、Windows/Android クライアントあり
- **Telegram Bot** / **Discord webhook** — 専用 bot・チャンネルに閉じる（プッシュ代替）
- **Firebase FCM + 専用プロジェクト** — 本格モバイル向け（実装コスト高）

選定基準: ma-home から HTTP で送れる / 受信側を ma 専用に閉じられる / quiet hours で mute 可能。

| 優先 | 項目 | メモ |
|------|------|------|
| 高 | **A4a** Outbound モデル | **済** — `channel` + `delivered`、gateway 直実行と一致 |
| 高 | **A4b** `chat_push` | **MVP 済**（bubble）。**目標**: SSE `room_inbound` |
| 中 | **A4c** `voice_surface` | **MVP 済**（Web Speech）。**目標**: 8090 TTS audio URL |
| 中 | **A4d** チャネル fan-out | enqueue → kiosk + push（A4g） |
| 中 | **A4e** nudge クールダウン | **済** |
| 中 | **A4f** tick スケジューラ | **済** — `run-autonomous-tick.ps1` + `install-autonomous-tick-task.ps1`（15m） |
| 中 | **A4g** `push_*`（**PC 本線**） | **済** — `outbound_push.py`（`PRESENCE_OUTBOUND_NTFY_URL` / Pushover） |
| 低 | **A4h** `push_android` | 同上（外出先） |
| 高 | **A4i** `room_inbound`（**キオスク本線**） | **済** — 中央ダイアログ着信 |
| 中 | **A4j** 着信 → 新規会話 + 送信 | **済** — 「返事する」で native chat |

**実装順（案）**: ~~A4i~~ → **A4j** → **A4f** → **A4g** → A4b+ SSE → A4c+ TTS → OL2

**段階（合意 2026-06-15）** — 目標は **SSE + Server TTS**。まず MVP で「届く」を証明する。

**配信モデル（合意 2026-06-16）— 選択肢 A: 部屋着信**

- nudge は **会話セッションに属さない**。`session_id` 未知でも届く
- **Surface（キオスク）** = 8090 部屋ページの **中央ダイアログ着信**（A4i）+ Web Speech / 将来 TTS
- **PC（ma-home デスク）** = **部屋 UI では届けない**。外部 Push（A4g: ntfy / Pushover 等）— 8090 を開いてなくても通知
- 着信から **新しい会話**（A4j）は **キオスク側のみ**。「返事する」→ 新規 `session_id` + **下書き返信を native chat 送信**（compose/plan 経由）
- JSONL には nudge 自体は書かない
- enqueue 時に **チャネル fan-out**（例: `kiosk` + `push_ntfy`）。PC 用 per-client poll は本線にしない（MVP の `web-*` ack は暫定・廃止予定）

**なぜ PC は外部 Push か**: 部屋に二重 UI（modal + toast）を載せない / PC は常時 8090 を見てない / gateway から HTTP 1 発で済む（WinRT 自前より ntfy 等が安い）

| 届け先 | 手段 | 実装 |
|--------|------|------|
| Surface キオスク | poll → **中央ダイアログ** | A4i + A4j |
| ma-home PC | **ntfy / Pushover / Telegram** 等 | A4g（enqueue フックで POST） |
| 外出先 Android | 同上クライアント | A4g/h |
| ma-home スピーカー only | `voice_local` | 既存 TTS |

| 段 | 見た目 | 音声 | 備考 |
|----|--------|------|------|
| **MVP（済）** | チャット bubble + per-client poll | Web Speech（kiosk） | 検証用。A4i で置き換え、PC poll はやめる |
| **A4i 本線** | キオスク **中央ダイアログ**（返事する／あとで） | Web Speech → TTS URL | **実装済み**（PC poll 廃止） |
| **A4j** | ダイアログ CTA → 新規会話 | — | **実装済み**（ヒューリスティック下書き + 自動送信） |
| **A4g** | OS / ntfy 通知 | 任意 | PC 本線。部屋を開いたら通常チャット |
| **目標** | kiosk: SSE `room_inbound` | Server TTS | push は従来どおり HTTP |

| 段 | A4b chat_push | A4c voice_surface | 備考 |
|----|---------------|-------------------|------|
| **MVP** | outbound poll + **暫定** bubble | ブラウザ **`speechSynthesis`** | JSONL を汚さない |
| **目標** | **`room_inbound`** on SSE / 着信バナー | ma-home 合成 → audio URL | セッション非依存 |

MVP チェックリスト:

- [x] **A4a** Outbound モデル + experience に `channel` / `delivered`
- [x] **A4e** nudge クールダウン（MVP 前に必須）
- [x] **A4b-mvp** `GET /api/v1/outbound/pending` + poll → bubble（暫定。A4i で着信 UI へ）
- [x] **A4c-mvp** 同上 payload の `speak` → Web Speech（`?kiosk=1`）
- [x] **A4b-mvp+** per-client ack（PC と Surface 両方に届く）
- [x] **A4i** 部屋着信バナー（キオスク中央ダイアログ。bubble / PC poll 廃止）
- [x] **A4j** 着信から新規会話 + 送信（着信文を compose プロンプトに同梱）
- [ ] **A4j+** 着信返信 UX — 下書き編集可（自動送信オプション）、`suggestInboundReplyText` 拡充
- [x] **A4b+** SSE `room_inbound` + 着信即時（poll はフォールバック 60s）
- [x] **A4c+** Server TTS URL + Web Audio（`POST/GET /api/v1/tts/surface`、Aivis/VOICEVOX）
- [x] **A4d-lite** kiosk-primary — Surface SSE alive 時は PC（Win/browser/voice_local）抑制、ntfy は維持
- [x] **A4d-lite+** `say` → kiosk — MCP `say` を `room_say` SSE + surface TTS へ（PC local 抑制）
- [ ] **A4d** チャネル選択（MVP 後）
- [x] **A4f** tick スケジューラ（desire-updater + `POST /api/v1/autonomous-tick`、Task 15m）
- [x] **A4g** Win Push（enqueue → ntfy / Pushover HTTP）
- [ ] **A4h** Android Push（ntfy クライアント共用で可）

---

## C — 部屋 UI（**Native 本線** — 次の主作業）

**方針変更（合意 2026-06-10）**

- **会話エンジン** = Native（`claude-code-server` → `/api/native/chat`）。8080 Node 層は段階的に外す
- **本番 URL** = これまでどおり `http://localhost:8090/`（視界・ステータス・レイアウトはこの殻を維持）
- **`poc-native.html`** = API 試験用のまま（本番見た目は `/` で作る）
- **やらない** = 8080 前提の UI 投資（プロジェクト/履歴プロキシ、`/api/abort` 転送の配線、8080 セッション削除 UI）

| 経路 | URL / 条件 | 用途 |
|------|-----------|------|
| こよりの部屋（本番） | `http://localhost:8090/` | Native 会話 + gateway（視界・status は 8090 独自） |
| Native 試験 | `PRESENCE_NATIVE_CHAT=1` → `/poc/native` | 最小 SSE テスタ（開発用） |
| レガシー | `POST /api/chat` → 8080 | **メンテのみ**。新機能は載せない |

| 優先 | 項目 | メモ |
|------|------|------|
| 高 | **C0 Native 既定 ON** | ma-home は `PRESENCE_NATIVE_CHAT=1` を install 時に書く |
| 高 | **C3 `/` チャット Native 化** | `app.js` → SSE `/api/native/chat`（8080 `/api/chat` を使わない） |
| 高 | **C4 セッション UI 再設計** | 8080 project/history 廃止 → `session_id` + 「新しい会話」 |
| 中 | **C5 キャンセル UI** | `AbortController`（poc-native パターンを `/` に） |
| 中 | **C6 Markdown 表示** | チャットログの読みやすさ |
| 高 | **C10 JSONL 履歴同期** | localStorage 廃止 → `~/.claude/projects/*.jsonl` を 8090 API 経由で全端末共有 |
| 中 | **C7 画面構成・レイアウト** | 視界・ステータス・チャットの調整 |
| 低 | **C8 デバッグ注入の非表示** | `gateway_turn_context` / `vision_prefetch` をユーザーに見せない |
| 後回し | **C9 8080 optional 化** | smoke / verify-mission-a を Native 対応。WebUI Task 外せる |

- [x] **C1** Native PoC 試験 — [docs/c1-native-poc.md](./c1-native-poc.md)（部分採用）
- [x] **C2** twicc 見送り — [docs/c2-twicc-decision.md](./c2-twicc-decision.md)
- [x] **C0** Native 既定 ON（`install-presence-ui-task.ps1` が初回 `presence-ui.local.env` を作成）
- [x] **C3** `/` チャット層 Native 化（`ui-config` + `app.js` SSE `/api/native/chat`）
- [x] **C4** セッション UI 再設計（localStorage 履歴・一覧・削除。8080 ワンショット取込 **完了** → UI 撤去）
- [x] **C5** キャンセル UI（「止める」ボタン + AbortController）
- [x] **C6** Markdown 表示（marked + DOMPurify、`static/vendor/` 同梱）
- [x] **C7** 画面構成・レイアウト（900px+ 2カラム: 会話｜視界+状態、`?kiosk=1`、キオスク URL 自動付与）
- [x] **C8** デバッグ注入の非表示（既定 OFF・会話ヘッダ右下「注入」トグルで表示切替）
- [x] **C9** 8080 optional 化（`post-logon-smoke` / `verify-mission-a` Native 経路、`install-webui-task` 任意明記）
- [x] **C10** JSONL 正本の履歴同期（`GET /api/v1/native/sessions` + messages、`app.js` 7s ポール・PC/キオスク共有）

| 優先 | 項目 | メモ |
|------|------|------|
| 高 | **C11 Surface タッチ / キオスク UX** | 実機 Surface 単体操作。Input Leap は自室用、持ち出しはタッチ必須 |
| 高 | **C11a** 即効 | 視界ちらつき修正、`touch-action` / 選択抑制、タップ 44px |
| 高 | **C11b** ドロワー | ハンバーガー + 全幅チャット、セッション・視界・状態を引き出し |
| 中 | **C11c** 視界強化 | ドロワー内大プレビュー / タップ全画面、1行キャプション |
| 中 | **C11d** 状態圧縮 | キオスク用サマリ2枚（話しかけていい？ / 気持ち1行）— 折りたたみカードで代替可 |
| 中 | **C11e** 右コンテキストレール | チャット左・常時/ピン留め右サイドバー。ドロワーで選んだ視界/状態カードを固定表示（Surface タッチ向け） |
| 中 | **C11g** スリープ / 画面消灯 | アイドル時 Surface 画面オフ、タッチで復帰。焼き付き・常時点灯対策 |

- [x] **C11a** タッチ即効（視界 img 差し替え、チャット pan-y、キオスク 44px）
- [x] **C11b** ドロワー UI（`?kiosk=1`、セッション操作・視界・状態・画面更新）
- [x] **C11b+** ドロワー scroll + 視界アスペクト追従（`room-drawer__body`、img `height:auto`）+ キオスク太スクロールバー（22px）
- [ ] **C11c** 視界強化（任意）
- [ ] **C11d** 状態圧縮（任意）
- [x] **C11e** 右コンテキストレール（視界/状態のピン留め、localStorage 永続、チャット左・レール右）
- [x] **C11d−** 状態カード折りたたみ（`[ いまの気持ち > ]`、レール/ドロワーは初期閉、開閉は localStorage）
- [x] **C11f+** キオスク音量スライダー — メニュー内 0–100%、localStorage、Aivis / Web Speech に適用
- [ ] **C11g** スリープ / 画面消灯 — アイドル N 分で画面オフ（`navigator.wakeLock` 解除 or OS 電源設定連携）、タップで復帰。SSE は維持 or バックグラウンド方針要検討

| 優先 | 項目 | メモ |
|------|------|------|
| 中 | **C12 Gateway + LLM ハイブリッド intent** | regex 即応 + ローカル LLM ルーター（曖昧な一文だけ分類） |
| 低 | **体温センサー（ma-home）** | WSL ではない → **LibreHardwareMonitor** 常駐で WMI 経由読取。未導入時は「センサーなし」 |
| 中 | **OL1 Open Loops 日付解決** | ingest 時 `明日`→`resolved_date`（JST）、類似 topic マージ、期限過ぎ auto-close |
| 中 | **OL2 リマインド配線** | 「○時にリマインド」→ `create_commitment(due_at)` + 定期 tick で say / UI 通知 |
| 低 | **OL3 Open Loops 運用** | stale 掃除 `purge-stale-open-loops.py`、ノイズは `purge-noise-open-loops.py` |

- [x] **OL0** stale open loop 掃除（`purge-stale-open-loops.py`、既定は resolved が今日より前、`--include-today` で当日分も）

- [x] **C11f** 部屋の空気 日本語化（`summary_for_prompt` + UI タグの availability/phase マップ）

- [ ] **C12** intent router（送信前に LM Studio で `desk|left|see|window|chat` 等を JSON 分類。regex 未検出 or 低 confidence 時のみ。Gateway 即実行 → 足りなければ compose/plan）

**実装順**: C0 → … → C10 → **C11** → **A4f → OL → A4g → C11g**（まー合意）→ **C12** / ビジョン（V）

---

## V — ビジョン / 未実装（`docs/web_ui_design.md`・`exported-session.md` より）

**注**: 8080 プロキシ本線・Native chat・キオスク着信・Tapo 視界・るな TTS 等は **実装済み**。以下は会話時点の**最終イメージ**でまだ残っているもの。

| 優先 | 項目 | メモ |
|------|------|------|
| 中 | **V1 感情色の部屋** | 会話画面の背景が `Emotion` に連動（Neutral=温かいグレー/薄緑/柔らかい紺。happy/curious/sad 等は export 案） |
| 低 | **V2 イントロ演出** | Embodied LLM スプラッシュ → こより顕在化（GIF/イラスト切替。朝=起きる/昼=歩く・伸び/終了=別演出）。表示中に status/camera ウォームアップ |
| 低 | **V3 発話ビジュアル** | るな再生中の波形 or 軽い動き（`web_ui_design` Task 6） |
| 中 | **V4 see_near（近目）** | Surface 内蔵カメラ → ma-home caption / 記憶。遠目=Tapo。→ [koyori-near-eye.md](./koyori-near-eye.md) |
| **高** | **V5 PC↔Surface 入力共有** | キオスクはタッチ+簡易KB。まー要望: **PC のキーボード・マウスを Surface 入力に**（BT キーボード切替は信用できずワンステップ余計）。Barrier / Input Leap / 有線・LAN 系を調査。ブラウザ内 KB 共有はハードル高（過去トライ） |
| 低 | **V6 家族・関係サイドバー** | ゴンザ・千ちゃん等の常時リスト（PoC では後回しと合意） |
| 低 | **V7 Phase 2 掃除** | `user_prompt.py` / `stripEnrichedUserPrompt` 削除（JSONL 履歴が純発話のみになった後） |
| 中 | **V8 room_say poll フォールバック** | SSE 未接続でも `room-say` 届く（`room_say_pending.py` WIP） |
| — | **V9 Linux Cage キオスク** | Ubuntu Server + cage + Chromium（`scripts/koyori-kiosk/`）。**現運用は Win Surface + `?kiosk=1`**。Linux 路は代替 |

- [ ] **V1** 感情色背景
- [ ] **V2** イントロ / スプラッシュ
- [ ] **V3** 発話インジケーター
- [ ] **V4** see_near
- [ ] **V5** PC キーボード・マウス → Surface（入力ストレス解消）
- [ ] **V6** 家族リスト UI
- [ ] **V7** enriched user 履歴後処理の削除
- [ ] **V8** room_say オフライン配信
- [ ] **V9** koyori Cage キオスク（任意・Linux 時）

---

## Web UI / Surface（C3–C8 に統合）

旧 8080 前提の「セッション削除 UI」等は **C4/C5（Native セッション）** へ置き換え。

---

## 手動・デバッグ早見

| スクリプト | 用途 |
|-----------|------|
| `purge-noise-open-loops.py` | エージェント台詞ノイズ loop を close |
| `purge-stale-open-loops.py` | 相対日付（明日等）が過去の open loop を close |
| `test-memory-stack.ps1` | 記憶スタック自動スモーク |
| `verify-mission-a.ps1` | ミッションA 一発確認（stack + 煎餅 + 任意 :8090 chat） |
| `watch-embodied-health.ps1` | ハング検出・daemon 再起動（手動 / Task から） |
| `install-embodied-watchdog-task.ps1` | 2分間隔 Watchdog Task 登録 |
| `run-memory-daemon.ps1` | :18900 前景起動 |
| `restart-presence-ui.ps1` | :8090 再起動（sociality 変更後は内部で sync-presence-deps も実行） |
| `sync-presence-deps.ps1` | presence-ui .venv へ orchestrator / relationship / **wifi-cam-mcp** 再ビルド |
| `c1-native-poc.ps1` | C1 Native PoC の ON/OFF + restart（`-Enable` / `-Disable` / `-Status`） |
| `run-webui-ma-home.ps1` | :8080 起動 |
| `test-gateway-direct-actions.ps1` | A3 gateway 直実行スモーク（observe / say / reflect） |
| `install-autonomous-tick-task.ps1` | A4f — 15m で desire-updater + autonomous-tick |
| `run-autonomous-tick.ps1` | A4f — 手動 1 回 tick（ログ付き） |
| `setup-ntfy-ma-home.ps1` | A4g — ntfy topic 生成 + `presence-ui.local.env` + テスト POST |
| `start-irodori-tts.ps1` | Irodori TTS Server `:8088`（参照声待ち・任意） |
| `tts_benchmark.py` | TTS コールド/ウォーム計測（`scripts/tts-samples/`） |

**Outbound スモーク**（PC `voice_local` + キオスク着信）:

```powershell
curl -X POST http://localhost:8090/api/v1/autonomous-tick `
  -H "Content-Type: application/json" `
  -d '{"smoke_action":"miss_companion","speech_text":"まー、おる？"}'
```

Surface `?kiosk=1` で着信 →「返事する」→ 新規会話に下書き返信が送られ、こよりが応答する。

**A4f 登録**（presence-ui 常駐が前提）:

```powershell
.\scripts\install-autonomous-tick-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-AutonomousTick
Get-Content $env:USERPROFILE\.config\embodied-claude\logs\autonomous-tick.log -Tail 5
```

**A4g Push** — 初回セットアップ:

```powershell
.\scripts\setup-ntfy-ma-home.ps1 -Topic koyori-ma-home
# subscribe 後:
.\scripts\restart-presence-ui.ps1
.\scripts\setup-ntfy-ma-home.ps1 -TestOnly
```

`presence-ui.local.env` に `PRESENCE_OUTBOUND_NTFY_URL` が書かれる（**コミットしない**）。ntfy.sh 無料枠は**アカウント不要**（topic 名＝秘密）。Pro で topic 予約可。

**前提**: LM Studio、`.claude/settings.local.json`、`.mcp.json`（memory は `uv run --no-sync`）
