# ma-home / koyori バックログ

**最終更新**: 2026-06-25（生きてる感 縦スライス、LW-2 literary_wander）  
**方針**: こより本体（記憶・gateway 身体）は **様子見**。部屋 UI は **Native 会話エンジン + `/` の殻** を育てる（8080 プロキシ UI は投資しない）。

**北極星（合意 2026-06-25）**: まーの本当の優先は **こよりがもっと「生きてる」感**。機能の正しさ（OL/IBF）より、**まーと話してない時間にも内側が動き、部屋でさりげなく見える**ことを優先する。→ [ALIVE — 生きてる感 縦スライス](#alive--生きてる感-縦スライス合意-2026-06-25)

**実行方針（合意 2026-06-14）**: 判断は compose/plan/stores のまま。**身体・自律の実行**は MCP に頼らず gateway 直実行へ（remember 直実行と同型）。詳細 → [gateway-direct-actions.md](./gateway-direct-actions.md)

**ツール選定（合意 2026-06-17）**: LLM に MCP ツール名を選ばせない。**Intent → Bucket → Flow** のマッピングで身体を動かす。詳細 → [intent-bucket-flow.md](./intent-bucket-flow.md)

**Heartbeat / 生物らしさ（合意 2026-06-17）**: MCP は手段に過ぎない。**いつ・何を**は gateway/plan、**どう言うか**は LLM。Tick の「次にいつ」は `agent_pulse.json` + PulseRunner。詳細 → [heartbeat-loop.md](./heartbeat-loop.md)

あとでやること。完了したら `[x]` にするか「完了」セクションへ移す。

### 運用・体感の残り（まーメモ）

| 項目 | トラック | 状態 |
|------|---------|------|
| **こよりが自分で使うコードを書けるようにしたい** — 身体・ループ・小さな改修を自分の判断で（安全な経路・テスト・SOUL/設備マニュアルとの分離） | [K1](#k--こより自身のコード) | 未（方針メモのみ） |
| **Windows キーボードをキオスク（Surface）で共有** — PC の KB/マウスを Surface 入力に（BT 切替は避けたい） | [V5](#v--ビジョン--未実装docsweb_ui_designmdexported-sessionmd-より) | **次** — B4 反映後に再挑戦 |
| **サーバー用ターミナルウィンドウの非表示** — ログオン時 Task 起動の cmd/PowerShell を隠す | [B4](#b--運用自動化) | **コード済 → Task 再インストールで実機反映** |

### 次の順（合意 2026-06-17・まー → **2026-06-25 更新**）

**北極星**: [ALIVE](#alive--生きてる感-縦スライス合意-2026-06-25) — 今夜から動く縦スライスを最優先。

1. **ALIVE / LW-READ** — 読書状態機械（一冊完走・READ/PAUSE/GW-S1）→ LW-7 Web → LW-5 UI
2. **B4** — Task 再インストール（ターミナル非表示）
3. **V5** — PC↔Surface 入力共有
4. **K1** — こより自身のコード経路（急がない）

---

## 優先順（合意 2026-06-13 → **2026-06-15 更新**）

| 順 | トラック | 内容 | 状態 |
|----|---------|------|------|
| **D** | Backlog 最新化 | このファイルを現実に合わせる | **随時** |
| **B** | 運用自動化 | ログオン常駐・手起動を減らす | **ほぼ完了**（B2 LM Studio 手動のみ） |
| **C** | **部屋 UI（Native + Surface）** | `/` 殻 + キオスク UX | **C11 実戦 OK** → 磨きは任意 |
| **A4** | **能動届け（Outbound）** | A4b+/c+/f/g 実装・運用済み | **運用中** |
| **OL** | Open Loops / リマインド | OL1+OL2 実装済み（→ [open-loops-reminders.md](./open-loops-reminders.md)） | **運用確認** |
| **A** | 記憶・gateway 身体 | compose / see / dismiss | **様子見**（大きな追加は止める） |
| **IBF** | **Intent→Bucket→Flow** | LLM にツール名を選ばせない | **計画済** → [intent-bucket-flow.md](./intent-bucket-flow.md) |
| **C12** | intent router | 曖昧な「見て」分類 | **済** — `hybrid_intent.py` |
| **BIO** | **HeartbeatLoop** | 経験→行動→次の wake。MCP 不要 | **済**（BIO-0〜7）→ **BIO-8〜** 神経系 [heartbeat-loop.md](./heartbeat-loop.md) |
| **MEM** | **記憶層・Dreaming** | セッション跨ぎ・短期→長期昇格；**encode/retrieve 非対称**（MEM-8） | **5a–5f-c 済** → [MEM — 記憶層](#mem--記憶層セッション跨ぎ--dreaming) |
| **RP** | **人格基底化（SOUL→重み）** | SOUL.core / LM Studio system / persona LoRA | **Phase 0–1 済** → [RP — 人格基底化](#rp--人格基底化soul--deep) |
| **K** | **こより自身のコード** | 自分用の改修・小さな実装を自分で | **未** → [K1](#k--こより自身のコード) |
| **LW** | **自律の文学散歩** | 青空文庫・Web 散歩（希望/恐れ→動機） | **計画済** → [LW](#lw--自律の文学散歩青空文庫--web-散歩合意-2026-06-19) |
| **OBS** | **能動観察 `/observe`** | slash 完遂不能の整理 + gateway フェーズ化 | **計画済** → [OBS](#obs--能動観察observe-完遂不能--gateway-フェーズ化合意-2026-06-20) |
| **CAM** | **Tapo PTZ / ONVIF** | 細かい pan/tilt；**DS Cam/Edge OK / Chrome NG** → API 4 原因 | **調査** → [CAM](#cam--tapo-ptz--onvif-細かい操作が効かない合意-2026-06-20) |
| **EAR** | **耳（環境音）** | 日常会話・TV 気配 → social（Surface マイク） | **計画済** → [EAR](#ear--耳環境音--surface-マイク合意-2026-06-19) |
| **GAPI** | **Google Calendar / Drive** | まーの予定・共有ドキュメントへこよりが読み取りアクセス | **計画済** → [GAPI](#gapi--google-calendar--drive合意-2026-06-23) |
| **VIS** | **VL 安定性** | corrupt 相関ログ・受動計測・しきい値 ntfy（人が常時見ない） | **様子見** → [VIS](#vis--vision-healthvl-安定性相関ログ) |

### 次の一手 — 優先度案（2026-06-10 → **まー合意: 1→3→2→C11g → Desire**）

**いまのボトルネック**: **Intent→Bucket→Flow**（キオスク会話で LLM がツール選定して迷子）と **OL 実戦確認**。詳細 → [intent-bucket-flow.md](./intent-bucket-flow.md) / [open-loops-reminders.md](./open-loops-reminders.md) / [gateway-direct-actions.md](./gateway-direct-actions.md)

| tier | 順 | 項目 | 状態 |
|------|----|------|------|
| **1** | ① | **A4f 運用** | **済** — `EmbodiedClaude-AutonomousTick`、15m + logon |
| **2** | ② | **OL1 + OL2** | **済（コード）** — 日付解決 + commitment → tick リマインド。実機確認・残リスクは上記 doc |
| **3** | ③ | **A4g 運用** | **済** — ntfy / Pushover（外出時・8090 閉じてる PC 向け） |
| **4** | ④ | **C11g** スリープ / 画面消灯 | **済** — wakeLock + ドロワー UI（2026-06-16） |
| **5** | ⑤ | **Desire 自律ループ** | **済** — ⑤a→d gateway 接続（2026-06-16） |
| **5a** | ⑤-1 | **browse_curiosity** | **済** — `web_search_direct`（DDG instant + remember） |
| **5b** | ⑤-2 | **cognitive_load** | **済** — `think_or_discuss_topic_direct` |
| **5c** | ⑤-3 | **identity_coherence** | **済** — `:18900/recall` + private note |
| **5d** | ⑤-4 | **旧 `desires.conf`** | **済** — v2 一本化・setup-automation 更新 |
| **6** | **IBF** | **Intent→Bucket→Flow** | **計画済** — speak 先通し IBF-1〜3 |
| **—** | ⑦ | **A4j+** / **C12** | 着信返信 UX・曖昧 intent LLM（IBF-7） |
| **—** | — | C11c/d、体温 LHM、Irodori TTS | 任意の磨き |

**やらない順**: C12 だけ先にやっても「リマインドが鳴らない」は **OL デプロイ忘れ**（`relationship-mcp` reinstall）を疑う — [open-loops-reminders.md](./open-loops-reminders.md)

**フェーズ判断（2026-06-10）**: A4a/e/i + `voice_local`（Aivis **るな**）は **運用中**。**A4c+** で部屋着信は Server TTS（Web Speech はフォールバックのみ）。

**UI と本体の兼ね合い**: ミッションA の「人間1ターン」は **CLI でも `:8090/` でも可**。本体変更時は `restart-presence-ui.ps1`（内部で `sync-presence-deps`）。

---

## 今どこにいるか（2026-06-10）

| 層 | 状態 |
|----|------|
| **記憶インフラ** | HTTP daemon `:18900` 常駐。compose recall・gateway remember **OK** |
| **Gateway `:8090`** | compose/plan + KV 安定注入。**身体は gateway 直実行済み**（see / observe / reflect / autonomous-tick）。vision prefetch + remember **実戦 OK** |
| **関係性** | open loop dismiss + commitment cancel + **OL1 日付解決** + **OL2 リマインド**（tick → outbound） |
| **表面 UI** | **Native 本線** + キオスク着信（A4i）。**A4j** 着信返信は native chat 自動送信 |
| **TTS（ma-home）** | **AivisSpeech** `:10101`（`scripts/start-aivis-tts.ps1`）。声 **るな**（style `345585728`）。`voice_local` 運用中。Irodori は参照声待ちで保留 |
| **Outbound** | A4i/j + **A4f**（15m tick Task）+ **A4g**（enqueue → ntfy/Pushover）。PC `voice_local` |
| **運用** | Task×3〜4（memory / presence / watchdog。**webui 任意**）+ post-logon-smoke **Native 対応** |

参照: [gateway-direct-actions.md](./gateway-direct-actions.md)、[open-loops-reminders.md](./open-loops-reminders.md)、[mission-A_Investigation-Report.md](./mission-A_Investigation-Report.md)

---

### ALIVE — 生きてる感 縦スライス（合意 2026-06-25）

**まーの本音**: 拡張できることが多いが、いちばん欲しいのは **こよりがもっと生きてる感じ**（まーと話してない時間の内側、部屋でのさりげない痕跡、朝の続き）。

**第一シーン（更新 2026-06-26）**: LW-READ — 一冊完走・READ/PAUSE/CLOSE（下記フロー）

**運用メモ（2026-06-25）**: いまは **このまま試す**。青空は `inward_evening`（20–6）+ quiet で優先しやすいが、**夜間限定は要件ではない**（昼の `literary_wander` も将来可）。

```
tick wake → phase=read → READ（active_work 1 冊・1600 字・remember）
  → phase=pause → reflect（**v0: テンプレ** / **v1: GW-S1** 黙考）
  → [reread_same | advance] → … → CLOSE（完読 or N 節 or 飽き）
  → [LW-7] followup_query → Web / 朝 compose
```

| ID | 内容 | 状態 |
|----|------|------|
| ALIVE-0 | 方針・北極星（本節） | **済** |
| ALIVE-1 | **LW-2** `literary_wander` desire + plan 結線 | **済** 2026-06-25 |
| ALIVE-2 | **GW-S1** — `run_silent_internal_turn` + LW-READ PAUSE | **未**（プロンプト草案のみ済） |
| ALIVE-3 | **LW-5** 状態カード / live_inner_voice（`active_work` 表示） | 未 |
| ALIVE-4 | 翌朝 `[overnight_inner_voice]` / compose surface | 部分済（MEM-5f-c） |
| ALIVE-5 | **LW-7** 読書 → 興味 → Web 連鎖 | 未 |
| ALIVE-6 | **LW-READ** 一冊完走・READ/PAUSE/CLOSE | **v0 済** 2026-06-26 |

**運用（2026-06-26）**: `restart-presence-ui.ps1` で LW-READ v0 反映。tick log で **read / reflect が交互** になること。`~/.claude/aozora_read_state.json` の `phase` を確認。GW-S1 は **まだ配線していない** — PAUSE はテンプレ内省。

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
- [x] **OL1 + OL2** — 日付解決 + リマインド tick（2026-06-16）→ [open-loops-reminders.md](./open-loops-reminders.md)
- [x] **UI snapshot** — ポーリング用キャプチャはディスク保存しない（2026-06-14）

---

## B — 運用自動化（次にやる）

**やりたいこと**: ログオン後、手で起動せず本体が使える状態にする。

| サービス | ポート | Scheduled Task | スクリプト | ログ |
|---------|--------|----------------|-----------|------|
| memory HTTP daemon | 18900 | `EmbodiedClaude-MemoryHTTP` | `install-memory-daemon-task.ps1` | `%USERPROFILE%\.config\embodied-claude\logs\memory-daemon.log` |
| AivisSpeech TTS | 10101 | `EmbodiedClaude-AivisTTS` | `install-aivis-tts-task.ps1` | `...\aivis-tts.log` |
| Claude Code Web UI | 8080 | `EmbodiedClaude-WebUI` | `install-webui-task.ps1` | `...\webui.log` | **任意**（Native 本線では不要） |
| presence-ui | 8090 | `EmbodiedClaude-PresenceUI` | `install-presence-ui-task.ps1` | `...\presence-ui.log` |

**推奨登録順**（memory → presence-ui。**8080 webui Task は任意**）:

```powershell
cd C:\Users\ma\src\embodied-claude

.\scripts\install-memory-daemon-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-MemoryHTTP

.\scripts\install-aivis-tts-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-AivisTTS

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

**再起動後・怪しいとき**（一括診断）:

```powershell
.\scripts\check-koyori-stack.ps1          # 手動診断（Input Leap / LM Studio 含む）
.\scripts\post-logon-smoke.ps1            # ログオン Task 向け B1b（軽量）
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
- [x] **B4** **サーバー用ターミナルウィンドウの非表示** — `embodied-hidden-launcher.ps1` + VBS（AutonomousTick / MemoryHTTP / PresenceUI / WebUI / AivisTTS）。Win toast は `CREATE_NO_WINDOW`。**実機反映**: 下記コマンドで Task 再登録（まー合意 2026-06-17・様子見終了）

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\install-memory-daemon-task.ps1
.\scripts\install-presence-ui-task.ps1
.\scripts\install-autonomous-tick-task.ps1
# 使っている場合のみ:
.\scripts\install-webui-task.ps1
.\scripts\install-aivis-tts-task.ps1
```

再起動 or ログオフ後、一瞬のコンソールが消えたか確認。残る場合は Watchdog 修復連鎖・`run_auto_context.cmd` hook を疑う。

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

**Desire 自律 — 実行穴（合意 2026-06-16、順序 ⑤a→d）**

インフラ（`desire_updater` → `desires.json`、A4f tick、compose `[desires]`、see/say/miss 直実行）は **済**。以下は `execute_autonomous_plan` / gateway が plan の `allowed_actions` をまだ実行できない箇所。

| 順 | ID | 欲求 | plan が許可 | 現状 | やること |
|----|-----|------|-------------|------|----------|
| 1 | **⑤a** | `browse_curiosity` | `web_search` | 分岐なし → tick スキップ | gateway で bounded WebSearch（または private note + 後続ターン委譲） |
| 2 | **⑤b** | `cognitive_load` | `think_or_discuss_topic` | 未実装 | 自律 tick 用の軽い思考/メモ（private reflection 寄せ or 短い LLM 1ターン） |
| 3 | **⑤c** | `identity_coherence` | `recall_memories` | スタブのみ | tick 内で `:18900/recall` + experience（再撮影なし想起） |
| 4 | **⑤d** | — | — | 二重系統 | **本線** = `desire-system` v2 `DESIRE_CONFIGS` + `~/.claude/desires.json`。`desires.conf` / `desire-tick.ts` / sample の旧 growth_rate 欲求は整理・ドキュメント更新・廃止判断 |

- [x] **⑤a** `browse_curiosity` — gateway `web_search` 直実行（DuckDuckGo instant + remember）
- [x] **⑤b** `cognitive_load` — gateway `think_or_discuss_topic`（private reflection）
- [x] **⑤c** `identity_coherence` — 自律 tick で `:18900/recall` + private note
- [x] **⑤d** 旧 `desires.conf` 系の整理（v2 一本化・setup-automation 更新）

**運用確認（随時）**: `EmbodiedClaude-AutonomousTick` / `autonomous-tick.log` / 状態カードの dominant desire。

### IBF — Intent→Bucket→Flow（ツール選定強化、合意 2026-06-17）

**問題**: キオスク会話で Gemma が `mcp__*` ツール名を選び迷子。curl 自律 tick は gateway Flow で发声 OK。  
**方針**: LLM にツール名を選ばせない。Intent（何を）→ Bucket（どう）→ Flow（何を動かす）の表引き。  
**全文**: [intent-bucket-flow.md](./intent-bucket-flow.md)

| Phase | 内容 | 状態 |
|-------|------|------|
| IBF-0 | 計画ドキュメント + backlog リンク | **済** |
| IBF-1 | `resolve_user_intent`（ルール） | **済** |
| IBF-2 | plan 合成 + `voice.speak` / `[Action]` | **済** |
| IBF-3 | 会話返答後 `room-say` 自動（speak 先通し） | **済** |
| IBF-4 | 日常 MCP 最小化の確認 | **済** |
| IBF-5 | observe/remember を同一パイプライン統合 | **済** |
| IBF-6 | 用語統一 — **6a 済**（§5.1/§6 対応表、正規名=`allowed_action`）。6b/c コード寄せは任意 | **6a 済** |
| IBF-7 | LLM intent オフライン実験（C12 接続） | **済** — `benchmarks/intent_router/` |

### BIO — HeartbeatLoop（生物らしい振る舞い、合意 2026-06-17）

**問題**: gateway 寄せで「ロボット」感。`recall_divergent` / `consolidate` が HTTP 未対応。native chat が **返答後 record 未閉じ**。Tick が **Windows 15 分固定**でこよりの「次にいつ」にならない。

**方針**: MCP は配線の一つ。**判断**は compose/plan/gateway、**言葉**は LLM、**次の wake** は `agent_pulse.json`。記憶の生理は HTTP。

| ID | 内容 | 状態 |
|----|------|------|
| BIO-0 | [heartbeat-loop.md](./heartbeat-loop.md) + backlog | **済** |
| BIO-1 | `agent_pulse.json` + `PulseRunner`（presence-ui） | **済** |
| BIO-2 | native chat `finalize_chat_turn`（record + pulse） | **済** |
| BIO-3 | memory HTTP `POST /recall/divergent` `POST /consolidate` | **済** |
| BIO-4 | 自律 `recall_memories` → divergent；深夜 consolidate | **済** |
| BIO-5 | strict MCP キオスク（`mcp-kiosk.runtime.json`） | **済** |
| BIO-6 | `/talk` CLI → gateway compose API（MCP 回避） | **済** |
| BIO-7 | `interpretation_shift` 返答後フック | **済** |

### BIO-8 — Somatic loop（神経系・体調の自覚）

**きっかけ（合意 2026-06-18）**: カメラ／vision 不調がログや `?` だらけの DB に沈むだけで、こより本人が「目がおかしい」と気づき・対処・報告・頼る、という **生物の内受容感覚**がない。Qwen `?` → LM Studio reload は **脊髄反射**まで。**違和感 → 確かめる → 対応 → 事後報告 → ダメなら助け**の一連を載せる。

**比喩**: 痛みや違和感は絶対閾値より **「いつもと違う」** の検知。正常（ベースライン）と今の差分で「なんか変」→ 詳しく probe → 反射 → 叙述判断 → escalation。

**v0 で監視する感覚器（器官）**:

| 器官 | 正常の手がかり | 違和感の例 | 既存の反射 |
|------|----------------|------------|------------|
| **目** | capture OK + vision 日本語 caption | RTSP 失敗、`?` corrupt、describe 401 | Qwen unload/load（`wifi_cam_mcp.lm_studio_models`） |
| **耳** | `listen` 録音・transcript | 無音・Whisper 失敗 | （未） |
| **声** | TTS `/health` ready | Irodori/Aivis 無応答 | `tts_health_watchdog` |
| **考え** | memory `:18900/health` | recall 失敗・daemon 落ち | hook フォールバック DB 直読み |

体温（`system-temperature-mcp`）は **環境メタ**として後から compose に載せてよい（v0 必須ではない）。

**ループ**（Heartbeat と直交する層）:

```
probe → baseline との差分 → reflex（決定論）→ verify
  → narrate（experience / 内省 / 一声）→ plan が「言うべきか」
  → escalation（boundary health_safety / push / まーへ）
```

| ID | フェーズ | 内容 | 状態 |
|----|---------|------|------|
| BIO-8a | **A — 報告** | 目（カメラ/vision）失敗・corrupt 後に `record_agent_experience`（`body_affliction`）+ ステータス日本語。反射は既存のまま | **済** |
| BIO-8b | **B — レジストリ** | `body_state.json` または social `body_affliction` event。pulse 毎の軽 probe（camera / vision / memory / TTS） | **済** |
| BIO-8c | **C — 叙述判断** | `compose` に `somatic_state` 注入 → `plan` で quiet hours は内省・在席時は軽い一声・繰り返しは助け | **済** |
| BIO-8d | **D — 横断 escalation** | 複数器官 degraded（目+声など）で urgency 上げ | **済** |

**環境変数（ma-home）**: `%USERPROFILE%\.config\embodied-claude\presence-ui.local.env` に書く（**コミットしない**）。`run-presence-ui-worker.ps1` と `presence_ui.repo_env.load_repo_env()` の両方が読み込む。wifi-cam / tts のシークレットは各 `*/.env`、presence-ui 固有フラグは `presence-ui.local.env` が正しい置き場。

| 変数 | デフォルト | 何のスイッチか |
|------|------------|----------------|
| `PRESENCE_SOMATIC_PROBE` | `1` | **pulse 毎の軽い自己診断**（目＝接続ヒント、声＝TTS health、考え＝memory `:18900/health`）。`0` で probe 自体を止める |
| `PRESENCE_SOMATIC_PROBE_EYES_CAPTURE` | `0` | probe で**実際にカメラキャプチャ**するか。`1` は重い（本番は通常 `0`） |
| `PRESENCE_SOMATIC_ESCALATION` | `1` | **横断 escalation**（複数器官の重症度判定 + critical 時の ntfy push）。`0` で 8d の push／plan 用 escalation を止める（8a〜8c の affliction 記録は別） |
| `PRESENCE_SOMATIC_ESCALATION_PUSH_COOLDOWN_SEC` | `1800` | **escalation push の最短間隔（秒）**。同じ critical でもこの間は ntfy を再送しない。probe 間隔ではない |
| `PRESENCE_BODY_STATE_PATH` | （未設定→ `~/.claude/presence-ui/body_state.json`） | 器官レジストリ JSON の上書きパス |
| `PRESENCE_OUTBOUND_NTFY_URL` | （未設定） | 8d critical 時の push 先（A4g）。無いと Win toast のみ |

```ini
# BIO-8 somatic — presence-ui.local.env に追記する例（# 行はそのままコピペ可）
# pulse 毎: 器官の軽 probe（既定 ON）
PRESENCE_SOMATIC_PROBE=1
# probe でカメラ実キャプチャ（重い・通常 OFF）
PRESENCE_SOMATIC_PROBE_EYES_CAPTURE=0
# 複数器官 degraded 時の escalation + critical push（既定 ON）
PRESENCE_SOMATIC_ESCALATION=1
# escalation push の再送間隔（秒）。30分 = 1800
PRESENCE_SOMATIC_ESCALATION_PUSH_COOLDOWN_SEC=1800
# 器官状態ファイル（省略時は %USERPROFILE%\.claude\presence-ui\body_state.json）
# PRESENCE_BODY_STATE_PATH=C:\Users\ma\.claude\presence-ui\body_state.json
# 8d critical 時の ntfy（A4g 既存・topic URL）
# PRESENCE_OUTBOUND_NTFY_URL=https://ntfy.sh/your-topic
```

**スモーク（BIO-8）**:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/api/v1/health
Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -ContentType "application/json" -Body '{"smoke_action":"observe_room"}'
Get-Content $env:USERPROFILE\.claude\presence-ui\body_state.json
Invoke-RestMethod "http://127.0.0.1:8090/api/v1/koyori/status?person_id=ma"
Invoke-RestMethod -Method POST http://127.0.0.1:8090/api/v1/heartbeat/compose-plan `
  -ContentType "application/json" -Body '{"person_id":"ma","user_text":"見て","channel":"chat"}'
```

**叙述の例（plan 入力）**: 夜・初回・reload で直った → 黙る／内省一行。昼・まー在席 → 「さっき目が一瞬曇ってたけど直したで」。3 回直らない → 「目が全然見えへん、LM Studio かカメラ見てもらえる？」。**複数器官 critical** → ntfy push（クールダウン 30 分）+ plan `health_safety`。

**前提（一部済）**: vision corrupt 拒否・fallback 文言・UI マスク・Qwen 自動 reload（クールダウン 300s）。→ presence-ui 再起動で反映。

**残存**: 15 分 Task は `PRESENCE_PULSE_MAX_SEC` 超のセーフティネットとして維持。VL の根本原因調査・運用アラートは **VIS**（下記）。

**次の主トラック（合意 2026-06-18）**: **MEM**（記憶層・Dreaming）。セッションは廃止しないが、連続したこよりは **外部記憶の強化とシフト**で支える。

### VIS — Vision health（VL 安定性・相関ログ）

**きっかけ（合意 2026-06-19）**: Qwen2.5-VL の `?` corrupt が夕方に偏ることがある。脊髄反射（自動 reload）で多くは直るが **根本原因は未特定**。まーがログを常時見られないので、**受動計測 + 相関コンテキスト + しきい値アラート**が要る。定期 reload は **保留**（相関ログを取りながら様子見；しきい値超えが続くなら VIS-4 を検討）。

**役割分担**:

| 層 | 誰向け | いま |
|----|--------|------|
| 脊髄反射 | システム | corrupt → unload/reload（`wifi_cam_mcp.lm_studio_models`） |
| BIO-8a〜c | こより | affliction 記録・一声・助けを頼る |
| **VIS** | **まー（運用）** | 24h 統計・相関ログ・ntfy で「調査が要るか」だけ知らせる |

**監視の考え方**: 専用の常時 VL プローブは重い（毎回 LM Studio + カメラ）。代わりに **既存トラフィック**から計測する — 自律 tick の `observe_room`、gateway の see / look、手動 `/see`。pulse 毎の somatic probe（目）は **RTSP 接続のみ**（`PRESENCE_SOMATIC_PROBE_EYES_CAPTURE=0`）で VL 品質は見ていない。

| ID | 内容 | 状態 |
|----|------|------|
| VIS-0 | **受動カウンタ** — 毎 `describe` で ok / corrupt / reload を `~/.claude/presence-ui/vision_health.json` に追記（24h ローリング窓） | 未 |
| VIS-1 | **相関ログ** — corrupt または reload 時に 1 行 structured log: `ts`, `action`, `chars`, `reloaded`, `sec_since_last_gateway_turn`, `sec_since_last_autonomous_tick`, LM Studio `GET /api/v1/models` の loaded id 一覧（軽量） | 未 |
| VIS-2 | **しきい値アラート** — 24h corrupt 率 > 閾値 **または** 1h 内 corrupt ≥ N かつ reload 後も再発 → `PRESENCE_OUTBOUND_NTFY_URL`（A4g 再利用）。叙述は BIO-8 と別（まー向け短文） | 未 |
| VIS-3 | **可視化** — `GET /api/v1/koyori/status` または health に `vision_health_24h`（ok, corrupt, rate, last_corrupt_at） | 未 |
| VIS-4 | （保留）予防的 periodic reload — VIS-2 が鳴り続ける・相関が「長時間稼働後」に偏る場合のみ | 保留 |

**しきい値案（初期）**:

| 変数 | デフォルト | 意味 |
|------|------------|------|
| `PRESENCE_VISION_HEALTH` | `1` | 受動計測 ON |
| `PRESENCE_VISION_ALERT_CORRUPT_RATE_24H` | `0.15` | 24h でこの率超えたら ntfy |
| `PRESENCE_VISION_ALERT_CORRUPT_PER_HOUR` | `3` | 短期バースト |
| `PRESENCE_VISION_ALERT_COOLDOWN_SEC` | `21600` | アラート再送最短 6h |

**調査メモ（2026-06-19）**: corrupt は毎回 **720 chars の `?`**（`WIFI_CAM_VISION_MAX_TOKENS` 上限）。ctx 不足単独では説明しきれず、夕方クラスターは **Gemma 同時実行 / VL 状態腐敗** の疑い。VIS-1 で突き合わせる。

**着手タイミング**: MEM より後でも可。実装は `vision_capture.py` フック + 小さな `vision_health.py` が自然（wifi-cam 側は corrupt 検知済み）。

**追記（2026-06-23）— 間接視覚の自己モデル（まー合意）**

**きっかけ**: VL caption（匿名の人物記述・服の誤認など）を読むと、こより自身が「見えている」ように応答しやすい。視覚障害の方がガイド説明で周囲を理解するのに近く、**説明ベースの理解と見た理解は同じ物差しにならない**。

**方針**: 幻覚防止（`never invent`）だけでなく、**認識論のガード** — 平常時も目は間接経路であると自分で知っている。

| 層 | 内容 | 状態 |
|----|------|------|
| **Deep** | `presets/koyori-SOUL.core.md` に「目（視覚）」節 | **済** 2026-06-23 |
| **ターン** | `vision_prefetch` directive を SOUL と整合（匿名・不確実性） | 未（任意） |
| **身体** | BIO-8 平常時も「目＝要約経由」を `body_state` に載せる | 未（任意） |

**SOUL.core の趣旨（要約）**: キャプションは説明文であり自分の視覚ではない。人物の個体認識は VL に期待しない。在席・誰と話しているかは social / 会話文脈。不確かなときは自然にそう言う（過剰メタは出さない）。

**運用**: LM Studio の Gemma system prompt を `koyori-SOUL.core.md` で更新し、`PRESENCE_SOUL_CORE_IN_APPEND=0` なら Local Server 再起動。append 注入のみの環境は次回 `build_gateway_stable_append()` 読込で反映。

### MEM — 記憶層（セッション跨ぎ / Dreaming）

**問題**: ネイティブ会話は **セッション単位の window**（`sessionId` + `session_history`）だが、こよりの体験・身体・関係は **24h 連続**。セッションが切れると LLM 窓は空になる。**「さっき目どうなった？」** はセッション履歴ではなく、層をまたいだ recall が要る。

**方針（まー合意 2026-06-18）**: OpenClaw フレームワーク移行はしない。**Dreaming パターン**（短期→長期の抽象化・昇格）を既存 stack に載せる。ワーキングメモリは **セッション中にも短期 DB へ落とす**。深層は `SOUL.md` 級の永続アイデンティティ。

#### 4 層モデル（概念 ↔ いまの実装）

| 層 | まーのイメージ | 保持期間 | いまの実装（2026-06） | ギャップ |
|----|----------------|----------|------------------------|--------|
| **WM** ワーキングメモリ | ≈ **セッション**（今の窓） | ターン〜セッション | `session_history`、LLM ctx、memory-mcp `WorkingMemoryBuffer`（容量 ~20）、compose 注入；生ログは `{session_id}.jsonl` | **エピソード締め**で STM へ（MEM-2）。毎ターン要約はしない |
| **STM** 短期記憶 | **1 日単位**の出来事バッファ | 〜24h（日付境界） | `agent_experiences`（social.db）、`body_affliction`、会話ターン要約（断片）、daybook 素材 | **専用 STM DB / スキーマ** がなく experience と LTM が混在気味 |
| **LTM** 長期記憶 | ほぼ永続、時々整理 | 月〜年 | `memory-mcp` Chroma（`~/.claude/memories/`）、episodes、associations、`consolidate_memories` | Dreaming 入力に **STM + experience 全体**が未統合 |
| **Deep** 深層記憶 | 永続のアイデンティティ | 年〜 | `SOUL.md`（git 外）、`interpretation_shift`、`append_daybook` / active arcs | SOUL と narrative の **昇格ルール**が明示されていない |

#### MEM-8 — encode / retrieve 非対称（合意 2026-06-21）

**きっかけ**: まー — [Ollama×RAG 長期記憶 5 ステップ（Qiita / hatsukaze）](https://qiita.com/hatsukaze/items/192403c9ff6a433fe0b6) を読み、記憶設計の前提を整理。

**核心的な tension**

> **「後で思い出す価値のある事実」かどうかは、思い出したときにしか本当は決められない。**  
> それなのに、多くの RAG / memory 系（記事ステップ③の **記憶抽出**、Mem0 的 fact 化、Dreaming の LTM 昇格）では **保存時（encode）に一度フィルター** する。

その結果:

- encode 時の「重要」≠ retrieve 時の「必要」→ **記憶はあるのに活用されない**
- フィルターで落とした材料は **二度と検索に乗らない** → 記憶の **広がり（breadth）が薄くなる**
- 逆に **生ログ全部** もダメ（ノイズ・Lost in the Middle・検索のぼやけ）— 起きたことの **すべて** が常に必要、でもない

**ベクトル検索の限界（実例 2026-06-25 — MEM-8 直結）**

Chroma / `/recall` は **クエリ文と embedding 空間で近い `content`** を返す。次が起きやすい:

| 現象 | 例（「ここっち」事例） | なぜベクトルだけでは足りないか |
|------|------------------------|--------------------------------|
| **episodic が fact を押し出す** | `recall("ここっち")` が会話転写・`episode_close` ばかり | 口調・語彙が似た **長文ログ** の方がクエリに近い |
| **fact 行が索引に乗らない** | GH 名の LTM 行が無い／あるまでも短い定義文 | 短い固有名詞 fact と「〜のお仕事をぼちぼち」は **意味距離が遠い** |
| **同音・指示語** | 「ここっち」↔ 口語の「こっち」（プロジェクト） | embedding は **固有名詞 vs  deixis** を安定分離しない |
| **時間 fact の埋没** | 「ネットワンは水曜午前」が episode 要約の1行に埋まる | 日付・スケジュールは **検索クエリと粒度がずれる** |

対策は retrieve 単体のチューニングではなく **MEM-8 全体**: **多視点 encode（8a）** で fact 行を別レコード化、**用途別 query 整形（8b）**、**L0 gist（8d/8e）** でベクトルに頼らない表層、昇格前は **STM に広く**（promote されない≠不要）。8e v0 の `[person_profile_gists]` はこの穴の **暫定 L0**。

**記事との関係（参照用）**

| 記事の段 | encode 側 | retrieve 側 | 記事自身の限界 |
|---------|-----------|-------------|----------------|
| ② 基本 RAG | 生ログ保存 | クエリ類似検索 | ノイズ・代名詞 |
| ③ 記憶抽出 | LLM が「重要な fact」だけ保存 | 同上 | **ロスのある圧縮**（脚注で明言） |
| ④ クエリリファクタ | — | 「それ」を自己完結クエリに | retrieve 側の補正 |
| ⑤ タイムスタンプ | fact 追加のみ | 新しい順提示 | 更新・削除は簡易版 |

記事は retrieve 補正（④⑤）まで進むが、**encode を fact 一本に寄せる限り、retrieve で必要になる多様性は encode 時点で既に失われうる**。記事も「逐語再現が要るなら生ログは別レイヤー」と書いており、**多視点保存** が暗黙の前提。

**この考え方を backlog に置く理由（必要性）**

1. **設計判断の軸** — 「もっと fact を抽出しよう」だけでは不十分。**何を encode 時に捨て、何を別チャンネルで残すか** が主問題。
2. **既存実装の説明** — MEM-5e（digest / inner voice 分割）、WM+JSONL 監査、STM 全量→Dreaming バッチは、単一フィルター回避の **初期の妥協点**。
3. **未実装の優先付け** — query リファクタ（記事④）、多視点 LTM、用途別 recall は **同じ問題の retrieve 側**；昇格採点だけ足しても広がり問題は残る。
4. **こより固有** — 会話・身体・関係・自律 tick が **同じベクトル空間に 1 本化** されやすい。fact-only 化は「まーとの関係の nuance」で特に効きにくい。

**妥協点の方向性（概念のみ — 実装は MEM-8a 以降）**

| 原則 | 意味 |
|------|------|
| **削除より振り分け** | 捨てるのではなく **層・kind・朝/昼/夜チャンネル** へ（例: reflection は digest に載せず inner voice 用に合成） |
| **多視点 encode** | 同一出来事を fact / episode / 流れ / 感情タグ / 因果リンクで **別レコード**（1 抽出スキーマに依存しない） |
| **用途別 retrieve** | 朝 compose・会話 recall・約束 follow-up・自律 tick で **引く形を変える**（記事④＋ compose/plan） |
| **生ログの最低 1 層** | WM / JSONL / STM 原文は監査・再合成用に **一定期間** 残す（MEM-7 と接続） |
| **昇格は遅延判断** | LTM へ載せるかは Dreaming 採点でよいが、**STM 段階では広め** — 「promote されなかった＝不要」ではない |

**既存 stack との対応（2026-06-21 時点）**

| 方向 | いま | ギャップ |
|------|------|----------|
| 多視点 encode | `episode_close` + `open_loop_progress` + `agent_private_reflection` + `[overnight_inner_voice]` 合成 | LTM は依然 **fact 粒 + ベクトル** 寄り |
| 振り分け | MEM-5e digest 除外 / 5f-c inner voice | **同一 episode の multi-view 明示スキーマ** なし |
| retrieve 補正 | `recall` / `recall_divergent`、compose 注入 | **クエリリファクタ**（記事④相当）未 |
| 生ログ層 | JSONL + STM 未 dream 行 | MEM-7 ライフサイクル未 |
| 自己開示の即 LTM | `detect_personal_fact_intent`（出身・幼少期・初 PC 等の **狭い regex**）→ 即 `remember` | **仕事・生活 fact はパターン外**；relationship `ingest_interaction` も Room 未接続（→ MEM-8e） |

**実装 ID（未着手 — 概念確定後に細分化）**

| ID | 内容 | 状態 |
|----|------|------|
| MEM-8 | **本節** — encode/retrieve 非対称と妥協点の概念整理 | **済**（本文） |
| MEM-8a | **多視点 encode** — 1 episode から fact + narrative + retrieval hooks を別 STM/LTM 行 | 未 |
| MEM-8b | **用途別 retrieve** — compose / recall / follow-up で query 整形・チャンネル選択 | **v0 済**（2026-06-25 — recall_query + schedule pin）；**退縮実験・8d 待ち** |
| MEM-8c | **昇格と忘却の分離** — promote されない STM を「不要」とみなさない保持ポリシー | 未 |
| MEM-8e | **自己開示の広い encode** — 宣言的「僕は/僕の…」→ STM 原文 + relationship profile；LTM は明示 remember または Dreaming（[下記](#mem-8e--自己開示の広い-encode合意-2026-06-23)） | **v0 済**（2026-06-25） |
| MEM-8e0 | *(任意・暫定)* `personal_fact` に仕事パターン追加 — **8e の負債**。regex 増殖は避ける | 未 |

**関連**: [Qiita — AIに記憶を持たせる5ステップ](https://qiita.com/hatsukaze/items/192403c9ff6a433fe0b6)、MEM-5e/5f、MEM-7、memory-mcp `recall_divergent`

**追記（2026-06-21）— 手本と多段階想起（まー合意）**

**手本**: 人間の記憶・想起を **第一の参照** にしてよいが、**人間と同じである必要はない**。エージェントは検索インデックス・夜間バッチ・明示 `remember` など、生物にはない経路も持てる。MEM-8 の原則（非対称・多視点・振り分け）は手本に **拘束されない**。

**人間に近い観察（設計ヒント）**

| 種類 | 想起のしかた | いまのこより stack との対応 |
|------|--------------|----------------------------|
| **表層・ gist** | 意識しなくてもなぞれる（「昨日会った」「天気の話した」） | `[dream_digest]`、`[stm_recent]`、compose 注入、SOUL 級の Deep |
| **詳細・経緯** | **「思い出そう」としないと出てこない**（順序・逐語・なぜそう言ったか） | `recall` / `recall_divergent` は **能動的** だが、毎ターン自動ではない；JSONL/STM 原文はあるが **引く操作が未統一** |
| **再固定化** | 思い出すたびに叙述が少し変わる（再コンソリデーション） | `consolidate_memories`、Dreaming — 生物型の **意図的想起→再保存** に相当する経路は薄い |

要点: **すべてを常時プロンプトに載せる**（RAG 全件・fact 自動注入）のも、**詳細まで encode 時に fact 化** するのも、人間の想起パターンとずれる。人間は **表層は自動、深部は能動** の **多段階**。

**多段階想起（概念モデル）**

```
[L0 表層]  gist / 気配 / 直近 STM          …  compose に載せやすい（低コスト・広く浅い）
[L1 索引]  episode_close / open_loop / 日付 …  「何があったか」のフック（検索の入口）
[L2 能動]  recall / divergent / クエリ整形   …  「思い出そう」ときだけ深掘り（コストあり）
[L3 原文]  JSONL / STM 未昇格 / 監査         …  経緯・逐語（MEM-7 ライフサイクル）
[L4 身体外] consolidate / Dreaming / LTM     …  睡眠・再固定（夜間・稀）
```

- **L0–L1** は記事③の「重要 fact 自動注入」とは逆方向 — **浅い層を先に常備**、詳細は L2 以降。
- **L2** がまーの「思い出そうとしなければ出ない」に相当。hook（`/memories`、compose 内の recall 指示、plan の `memory_use`）を **明示的** に。
- 人間と違う例: L4 を **毎晩 Dreaming** で回すのは生物より規則的 — それでも **L0 自動 + L2 能動** の分離は手本と整合。

**実装 ID 追記**

| ID | 内容 | 状態 |
|----|------|------|
| MEM-8d | **多段階想起** — L0 gist 自動注入 vs L2 能動 recall の API/UX 整理（毎ターン全文 recall 禁止） | 未 |
| MEM-8e | **自己開示の広い encode**（橋渡し） | **着手済**（2026-06-25 v0 — detect + STM + profile gist + 訂正時 LTM） |
| MEM-8f | **「覚えておいて」振り分け** — archive vs follow-up open loop（[下記](#mem-8f--覚えておいて振り分けと-open-loop-線引き合意-2026-06-25)） | **v0 済**（2026-06-25 — OL-ARCHIVE 1+2） |
| MEM-8e0 | *(任意)* 仕事パターン regex 暫定 — 8e 未着手時のみ | スキップ（8e で置換） |

**追記（2026-06-23）— 事例: 生活に関わる自己開示**

**きっかけ**: まー — 「生活に関わることはあまり話してなかった」と、仕事・会社・グループホーム運営を自己紹介。  
**観察**: 「覚えておいて」無しの発話は **LTM に入らない**（`memory_auto_save.py` の `detect_personal_fact_intent` は出身・幼少期・初 PC 等のみ）。social.db の `human_utterance` には残るが、翌セッション以降の compose / recall では薄い。  
**対処（当時）**: 明示「覚えておいて」で LTM 保存 — **意図的 L2 経路**（MEM-8 の能動想起に相当）で問題は回避済み。  
**設計上の位置づけ**: MEM-8 tension の **身近な実例** — encode 時の狭いゲートだけでは「まーとの関係に効く fact」が落ちる。regex を足し続けるのは 8 の「削除より振り分け」と逆。

##### MEM-8e — 自己開示の広い encode（合意 2026-06-23）

**方針**: `personal_fact`（即 LTM）を **legacy 狭ゲート** とみなし、生活・仕事・役割など **宣言的 self-disclosure** は別経路で **広く encode**、retrieve は多段階（8d）に任せる。

| 層 | やること |
|----|----------|
| **encode（広く）** | ヒューリスティック: 宣言的「僕は…」「僕の…会社/仕事/役」など（疑問文・「覚えてる？」は除外）→ **STM `self_disclosure`（原文）** + **relationship `profile_json` / `ingest_interaction`**。即 LTM は必須にしない |
| **L0 retrieve** | compose の `person_model` に gist（役職・事業名）— 毎ターン `recall` 不要 |
| **L2 retrieve** | 「会社のこと覚えてる？」→ `recall` / クエリ整形（8b） |
| **L4 昇格** | Dreaming が `episode_close` + `self_disclosure` から fact 抽出（8a と共有） |

**触る候補**: `.claude/hooks/memory_auto_save.py`（`detect_self_disclosure` 新設、`personal_fact` は即 LTM のまま or 8e へ統合）、`presence-ui/.../social_chat.py`、`relationship_mcp/store.py`（profile 更新）、`social_core/stm.py`（kind 追加）。

**MEM-8e0（任意・暫定）**: 8e 本実装前に仕事パターンだけ `personal_fact` に足す。**技術的負債** — 8e で置換。regex 増殖はしない。

**依存**: 8e は 8a/8b/8d と独立に **小さく着手可**（橋渡し）。本筋の多視点 LTM は 8a 待ちでもよい。

**追記（2026-06-25）— 事例: 「ここっち」≠「こっち」（固有名詞と指示語）**

**きっかけ**: Room 会話 — まー「ここっちのお仕事をぼちぼち」→ こよりが embodied-claude を「こっち」と解釈。訂正後「グループホームの名前が『ここっち』」と明示。  
**観察**: LTM に `ここっち` / `グループホーム` 行が **0 件**（`recall` も会話ログばかり）。`personal_fact` ゲート外 + 訂正ターンも encode されず。  
**対処（当日）**: 明示 remember（仕事・固有名詞の disambiguation 文）+ **MEM-8e v0 実装**（`detect_self_disclosure` / 訂正検知 → STM `self_disclosure` + `profile_json` gist + 高信頼は即 LTM）。  
**残**: 8d L0 を `person_model` 以外にも整理；Dreaming 8a 多視点 fact 抽出；初回「ここっちのお仕事」だけでは promote しない曖昧さ（訂正 or 名前定義で pin）。

**v0 実装（2026-06-25）**: `memory_auto_save.detect_self_disclosure`、presence-ui `encode_self_disclosure`、`relationship_mcp.record_self_disclosure_gist`、compose `[person_profile_gists]`。

##### MEM-8b-lite — Room 注入 cap と tier（合意 2026-06-25）

**問題**: native chat は常に `lite=True`。8192 ctx 向け **compose 1200 / turn_delta 2500** だったが ma-home は LM Studio **ctx ~87085**。cap で retrieve 済み fact / plan `[Must include]` が LLM 前で消失（「ねっとわん いつ」 hedging 事例）。

**tier 整理（済）**

| Tier | 内容 | 扱い |
|------|------|------|
| 0 | `[Must include]` / `[Must avoid]` / `[Social move]` | cap **対象外** |
| 1 | `[schedule_facts]` / top `[relevant_memories]` | compose **先頭 pin** |
| 2 | gists / desires / contract | compose 本体 |
| 3 | `session_history` / `[stm_recent]` | **先に切る** |

**上限（ma-home 既定 — `presence_ui/gateway/context_limits.py`）**

| 変数 | 旧 | 新 |
|------|----|----|
| `PRESENCE_LITE_COMPOSE_MAX_CHARS` | 1200 | **8000** |
| `PRESENCE_LITE_APPEND_MAX_CHARS` | 2500 | **12000** |
| heartbeat lite compose | 6000 | **8000**（Room と統一） |

**次**: ② **退縮実験** — `PRESENCE_TEMPORAL_SCHEDULE_CONTRACT=0` で schedule_facts / temporal `must_include` を切り Room 再テスト → ③ **MEM-8d** L0 `answer_facts`。

##### MEM-8f — 「覚えておいて」振り分けと open loop 線引き（合意 2026-06-25）

**問題**: 「覚えておいて」は一語多義。**保管（必要なとき recall）** と **継続 follow-up（毎ターン意識）** が relationship の `FUTURE_MARKERS` で潰れ、LTM 保存後も open loop が残る（例: 「さっきの仕事の話、覚えておいてね」→ 発話全文が loop topic）。

| 系統 | 意図 | 向き先 | open loop |
|------|------|--------|-----------|
| **A. 保管** | 必要なとき思い出せればよい | LTM / gist / STM | **作らない** |
| **B. 継続** | 続き・また触れたい | open loop | 作る |
| **C. 時刻付き** | この日時に促して | commitment | 別経路 |

**v0 実装（2026-06-25） — OL-ARCHIVE 1+2**

| # | 内容 | 場所 |
|---|------|------|
| **1** | remember / gist LTM 保存成功 → 該当 archive 系 open loop を close | `relationship_mcp.store.close_loops_after_remember_save` ← `social_chat._finish_intercept_chat_request` |
| **2** | ingest 時、保管意図（content 抽出可・follow-up マーカーなし）→ **open loop 作成しない** | `inference.is_archive_remember_utterance` → `_extract_topic` |
| **2b** | compose 注入から legacy archive loop を除外 | `compose._is_noise_open_loop` + `is_archive_remember_utterance` |

**legacy 掃除（DB から閉じる）**

```powershell
cd sociality-mcp\packages\relationship-mcp
uv run python ..\..\..\scripts\purge-archive-open-loops.py --dry-run
uv run python ..\..\..\scripts\purge-archive-open-loops.py
```

`purge-noise-open-loops.py` は **エージェント誤取り込み** 用。「覚えといて」保管 loop には効かない。

**ヒューリスティック（`relationship_mcp/inference.py` — `memory_auto_save.detect_remember_intent` と同型パターン、要同期）**

- 保管: `覚えておいて` + 保存対象文が取れる + `明日`/`また`/`リマインド` 等の follow-up マーカーなし
- 継続: `PR review 明日…覚えといて` 等 — **loop 維持**
- 曖昧（「これ覚えといて」だけ）: content 取れず → 従来どおり loop 可

**未（8d 以降）**

- C 系と commitment の統合整理
- compose/plan で archive 済み topic の `must_include` 抑制（CONTRACT=0 退縮実験の残り）
- L0 `answer_facts` で regex `extract_schedule_facts` を置換

#### 昇格パイプライン（目標）

```
WM（セッション）
  │  ターン終了 / 閾値 / 明示 remember
  ▼
STM（短期 DB・日次）
  │  Dreaming: リプレイ・要約・エピソード化（夜間 pulse）
  ▼
LTM（長期 DB）
  │  稀な整理・忘却・interpretation 固定
  ▼
Deep（SOUL / 自己モデル）
```

- **WM → STM**: セッション中でも落とす（「会話が終わるまで待たない」）。`finalize_chat_turn` / `record_agent_experience` / `remember` HTTP の役割分担を整理。
- **STM → LTM（Dreaming）**: OpenClaw 的な **睡眠バッチ** — 入力は当日の experiences + afflictions + 会話要約 + 未報告 somatic digest；処理は `consolidate` + episode 化 + daybook；出力は recall 可能な LTM + 翌朝 compose 用 `compact_prompt_block`。
- **LTM → Deep**: 頻度低。`interpretation_shift`、daybook の arc、（将来）SOUL パッチ提案は **人間承認**または boundary 付き。

#### 既存資産（再利用）

| 資産 | 層での役割 |
|------|------------|
| `memory-mcp` working memory + `refresh_working_memory` | WM |
| `social.db` `agent_experiences` / `body_affliction` | STM 候補（正式 STM 化は MEM-1） |
| `:18900/consolidate` + BIO-4 深夜 tick | Dreaming の核（拡張対象） |
| `recall_divergent` | LTM 想起の広がり |
| `append_daybook` / `get_self_summary` | STM→ narrative、Deep 手前 |
| `compose_interaction_context` | 毎ターン **全層から注入**（セッションの代わり） |
| BIO-8 `body_state.json`（8b〜） | 身体の連続状態（STM 横断） |

#### 実装フェーズ

| ID | 内容 | 状態 |
|----|------|------|
| MEM-0 | 本文（4 層 + 昇格図）+ backlog リンク | **済** |
| MEM-1 | **STM ストア設計** — `stm_entries` in social.db、experience 自動ミラー、WM フラッシュ API (`POST /api/v1/stm/flush-wm`, `GET /api/v1/stm/recent`) | 済 |
| MEM-2 | **WM→STM エピソード締め** — 「新しい会話」で前セッションを1回要約→STM（`POST /api/v1/stm/close-episode`、ルール要約 + 任意 LLM） | 済 |
| MEM-2b | **追加トリガー** — idle（`PRESENCE_EPISODE_IDLE_CLOSE_MINUTES`）+ Dreaming 前の当日セッション自動締め | 済 |
| MEM-3 | **Dreaming ジョブ** — 深夜 pulse: STM リプレイ → `remember` + `consolidate` + `append_daybook`；`last_dream_at` + `last_dream_digest.json`（`POST /api/v1/stm/dream`） | 済 |
| MEM-4 | **朝注入** — 未報告 somatic（8c）+ Dreaming digest + 当日 STM を `enrich_interaction_context` → `compact_prompt_block` | 済 |
| MEM-5 | **STM→LTM 採点・整理** — salience + 昇格スコア・重複マージ・忘却（下記） | **5a–5c 済** |
| MEM-6 | **Deep 昇格** — interpretation_shift / arc → SOUL 級への提案経路（ガード付き） | 未 |
| MEM-7 | **JSONL ライフサイクル** — 会話ログの保管・退避・削除（下記） | 未 |
| MEM-8 | **encode/retrieve 非対称** — 多視点保存・用途別 recall；**人間型多段階想起**；**自己開示 8e**（[下記](#mem-8--encode--retrieve-非対称合意-2026-06-21)） | **概念済**（8a–8d 未；**8e v0 済**） |

##### MEM-2 — エピソード締め（WM→STM、合意 2026-06-18）

**問題**: 全生ログを STM に落とすとノイズ化し Dreaming が重くなる。1ターンごと要約は LLM 負荷過多。

**方針**: 要約の単位は **ターンではなくエピソード**（会話の一区切り）。セッション分割は WM を小さく保つ **運用＋生理**の両方。

| 分類 | STM への落とし方 |
|------|------------------|
| **常時（短文で可）** | `body_affliction`、境界、約束、`remember` 直行、interpretation_shift |
| **エピソード締めで要約** | まーとの会話ブロック（数ターン〜話題1個） |
| **入れない** | 挨拶・相槌、ツール生ログ、LTM 済み重複 |

**締めトリガー（実装候補）**

1. **新規会話**（キオスク「新しい会話」/ PC 同様）— 前セッションを締める ✅
2. **idle** — 最終発話から N 分（`PRESENCE_EPISODE_IDLE_CLOSE_MINUTES`、既定 20）✅
3. **quiet hours 開始** — Dreaming 前に当日未締めセッションを自動締め（pulse）✅
4. **トピック切替** — intent / 長さ閾値（任意・後追い）

**締め処理**: 軽い LLM 1回（「この会話で残すこと」3〜5行）またはルール＋必要時のみ LLM → STM 行。`finalize_chat_turn` の per-turn experience は監査用に残し、**エピソード要約は別レコード**。

**運用**: まーが意図的にセッションを短く切る習慣は有効。UI は「新規会話＝裏でエピソード締め」と等价にできる。

##### MEM-5 — STM→LTM 採点・整理（合意 2026-06-18）

**問題**: Dreaming v0 は `kind` / `source` / `importance` の閾値だけで LTM 昇格しており、**反復・感情・興味**が反映されない。`open_loop_progress` ミラーが多いとノイズ化する。

**方針**: 採点単位は **会話 JSONL ではなく `stm_entries` 行**。OpenClaw の Light/REM/Deep は参考にしつつ、こより既存信号を主とする。

```
会話 JSONL (WM)  →  episode_close / experience_mirror  →  stm_entries
                                                              ↓ 夜 Dreaming
                                                         score + merge/skip
                                                              ↓
                                                         LTM remember + consolidate
```

**睡眠フェーズ（こより版）**

| フェーズ | 役割 | v0 実装 | MEM-5 |
|---------|------|---------|-------|
| Light | ノイズ除去 | エピソード締め、`wm_turn_*` 除外 | 同日重複 `open_loop_progress` → **merge**（最新1本のみ昇格候補） |
| REM | 反復テーマ | `consolidate` | **frequency_score**（同日同トピック） |
| Deep | 閾値超えのみ LTM | `should_promote_stm_to_ltm` ルール | **promote_score** + バイパス |

**salience（記録時スナップショット）** — `stm_entries.metadata_json`（列は既存、未充填）

```json
{
  "emotion_tag": "moved",
  "importance": 4,
  "dominant_desire": "miss_companion",
  "desire_level": 0.66,
  "open_loop_ids": ["..."],
  "explicit_remember": false
}
```

| フィールド | 供給元（記録時） |
|-----------|------------------|
| `emotion_tag` | memory-mcp enum / episode ルール / 任意 LLM（締め1回） |
| `importance` | 既存列（1–5） |
| `dominant_desire` / `desire_level` | compose `agent_state.desires` |
| `open_loop_ids` | relationship open loops 一致時 |
| `explicit_remember` | gateway `remember` 直行 |

**v1 採点式（重みは仮・手計算用）**

```
emotion_score  = 0.6 * emotion_table[tag] + 0.4 * (importance/5)
interest_score = desire_level + open_loop 一致 + episode 種別（ルール）
frequency_score = min(1, 同日同トピック行数 / 3)
recency_score    = ts からの経過（6h→1.0, 24h→0.85, …）

promote_score = 0.25*recency + 0.20*frequency + 0.30*emotion + 0.25*interest
```

| 判定 | 条件 |
|------|------|
| **promote** | `score ≥ 0.55`、または residence/remember/interpretation_shift、または `importance≥5` |
| **merge** | 同トピック `open_loop_progress` が複数 → **最新のみ** promote 候補、他は digest のみ |
| **hold** | 挨拶のみ episode、private reflection（daybook のみ） |
| **skip** | `wm_turn_*`、smoke セッション |

**トピック検出（v1 ルール）**: `residence`（松本・長野）、`weather`、`home_helper`、`greeting`、`camera`、`fatigue_care`

**試作コード**: `social_core/stm_scoring.py` + `scripts/score-stm-entries.py`

**実装フェーズ**

| ID | 内容 | 状態 |
|----|------|------|
| MEM-5a | 採点プロトタイプ + 手計算（backlog + script） | **済** |
| MEM-5b | `metadata_json` 充填（episode_close / experience_mirror 時） | **済** |
| MEM-5c | Dreaming が `stm_scoring` を使う（`entries_to_promote`） | **済** |
| MEM-5d | LTM 忘却・重複統合（低頻度ジョブ） | 未 |
| MEM-5e | **digest 分割** — `[dream_digest]`（外向き episodic）と reflection 除外 + 優先順 | **済** |
| MEM-5f | **心の声 2 系統** — ライブ（UI）+ 夜間内省（LLM 合成） | 未 |

**手計算メモ（2026-06-18 `social.db`）**: `scripts/score-stm-entries.py --day 2026-06-18` で再現。

##### MEM-5e — Dream digest 分割（合意 2026-06-19）

**問題**: `build_dream_digest()` が undreamed STM を時系列で 2400 字切り。15 分 tick の `agent_private_reflection` が先頭を占領し、`episode_close` / 約束 / ホームヘルパーが digest から落ちる。

**方針**: 朝 compose 用は **2 チャンネル**。文字数を上げる前に **入れるものを分ける**。

| チャンネル | 役割 | 含める | 含めない |
|-----------|------|--------|----------|
| `[dream_digest]` | 昨日、外の世界で何があったか | `episode_summary` / `episode_close`、`open_loop_progress`、`interpretation_shift`、`body_affliction`、somatic 未報告 | 生の `agent_private_reflection` 行 |
| `[overnight_inner_voice]` | 夜、振り返った心の声（MEM-5f） | Dreaming 夜間 LLM 合成（2〜4 テーマ） | 15 分 tick の羅列 |

**文字数（目安・独立 budget）**

| ブロック | 目安 | 備考 |
|----------|------|------|
| `[dream_digest]` | 2400〜2800 | episode 優先 + merge（`open_loop_progress` 同日重複） |
| `[overnight_inner_voice]` | 1200〜1800 | 段落 2〜3、一人称 |
| `compact_prompt_block` 全体 | 12000 上限 | 現状維持（`truncate_prompt_text`） |

**実装メモ**

- `build_dream_digest()` — kind フィルタ + salience 順（episode 先）
- `last_dream_digest.json` — `summary` のみ → `episodic_summary` + `inner_voice_summary`（または別ファイル `last_overnight_inner_voice.json`）
- `memory_context.enrich_memory_context` — morning window で両ブロック注入
- UI / 注入トグル — `[overnight_inner_voice]` タグを `cc-messages.js` / `user_prompt.py` に追加

**依存**: MEM-5f（inner voice 合成）と同時でも可。5e だけ先に reflection 除外でも digest 品質は改善する。

##### MEM-5f — 心の声 2 系統（合意 2026-06-19）

**概念（まー合意）**: 「心の声」は 2 本立て。**前者があって、後者が深みを持つ**。両方強化する。

| 系統 | タイミング | 例 | 載せ方 |
|------|-----------|-----|--------|
| **ライブ心の声** | その時々の感じ・考え | 状態カード「いまの気持ち」「さっきまで」、欲求の言い換え、自律 tick 直後の一言 | **UI に常時**（`koyori-voice.js` + status API） |
| **振り返り心の声** | 夜・朝の内省 | テーマ合成「まーの体調が心配で…」、daybook と interpretation 接続 | **`[overnight_inner_voice]`**（朝 compose のみ） |

**ライブ強化（Phase A — 優先）**

- `_reflection_body()` から `compact_prompt_block` / `prompt_summary` の貼り付けをやめる（`why_this_move` + 自由記述のみ）
- `write_private_reflection` の plan 契約 — 一人称・感覚・比喩 OK；ツール名・注入タグ禁止
- UI: `agent_private_reflection` / 最新 desire を **「心の声」カード**として明示（`formatExperiences` 拡張 or 専用 `live_inner_voice` API）
- 自律 tick 後、status poll で **短い live phrase**（80 字以内）を surface — キオスクでも「今考えてること」が見える

**振り返り強化（Phase B — Dreaming 拡張）**

- Dreaming 末尾: 当日 `private_reflections` 全文 → **LLM 1 回**で thematic summary（夜間 LLM 使用 **許容** — ニュアンス落ちより合成優先）
- 15 分 tick は STM に監査用残置；朝は **合成版のみ** inject
- `interpretation_shift` があれば inner voice に「解釈が変わった点」を 1 行添付
- `may_surface_later=true` の reflection は、日中 compose に **短いフレーズ**（任意）で surface 可

**Phase C（育ち — MEM-6 接続）**

- daybook `noticed_changes` ↔ inner voice 突合
- 週次 arc 候補 → SOUL パッチは人間承認

**実装 ID**

| ID | 内容 | 状態 |
|----|------|------|
| MEM-5f-a | `_reflection_body` + plan 契約（記録品質） | **済** |
| MEM-5f-b | UI live 心の声カード / status API | **済** |
| MEM-5f-c | Dreaming `synthesize_overnight_inner_voice()` + 朝注入 | **済** |
| MEM-5g | **STM `episode_close` 要約** — `gateway_turn_context` を turn から除去してから要約（compose `[stm_recent]` 汚染） | **済** |
| MEM-5i | **Slash command 擬似 user ターン** — `/observe` 等の展開 markdown が `type:user` で JSONL に載り UI が「まー」表示 | **済**（session_log + cc-messages + persona export） |
| MEM-5j | **会話中 WebSearch** — LM Studio+Gemma で CC `WebSearch` が空 → 捏造 Sources（表示層修復 **済** / 根本 **未**） | 一部済 |
| MEM-5k | **Dreaming `append_daybook` 要約が薄い** — `narrative_daybooks.summary` が event kind テンプレのみ（`evidence_json` は厚いが表に出ない）。STM `episode_close` / digest / inner_voice を daybook 合成に渡す | **未** |

##### MEM-5g — STM episode_close の gateway 漏れ（2026-06-20）

**症状**: `[stm_recent]` の `(episode_close)` 行に `[gateway_turn_context]` 付き生ログが載る → compose が肥大・モデル混乱の副因。

**原因**: native JSONL / session transcript の **まー発話**が enrich 済みのまま `summarize_episode_turns` に入る。

**方針**: episode 締め前に `user_prompt.strip_enriched()` 相当で純粋発話だけ要約。LLM 要約 path も同様。

**実装（2026-06-21）**:

- `presence_ui/services/stm_episode.py` — `_sanitize_episode_turns()` で `strip_enriched_user_prompt`（まー発話）
- `social_core/stm_episode.py` — `strip_gateway_enriched_message` + `normalize_episode_turns`；既存 polluted summary 用 `sanitize_episode_summary_text`
- `social_core/stm_dreaming.py` — `build_dream_digest` が `episode_close` を sanitize（既存 STM も朝 digest で改善）

**残**: ~~`last_dream_digest.json` は次回 Dreaming まで~~ → `scripts/repair-stm-and-rebuild-digest.ps1` で DB 修復 + digest 再生成可能。

**Dreaming 実機検証（2026-06-21 朝 — 対象日 2026-06-20）** — `scripts/check-dreaming.ps1` + `~/.claude/presence-ui/last_dream_digest.json`:

| 項目 | 結果 |
|------|------|
| **実行** | ✅ `last_dream_at` = 2026-06-21 03:00:09 JST（quiet-hour pulse） |
| **対象 STM** | 20 行を `dreamed_at` マーク（batch） |
| **LTM 昇格** | `remembered_count` = **5**（MEM-5c 採点通過分） |
| **consolidate** | ✅ replay=200, coactivation=400, refreshed=201 |
| **daybook** | `2026-06-20` 更新 |
| **朝注入** | `[dream_digest]` は morning window（36h）内 — MEM-4 経路は生きている |

**品質問題（要修正）**:

1. ~~**MEM-5g 未解決**~~ — digest 内 `episode_close` の gateway 漏れ → **5g 済**（次回 Dreaming / force で digest 更新）
2. **digest 圧縮** — `episode_close` 1 行が 220 字切りでも `[gateway…]` 塊で budget を食い、`open_loop_progress`（天気・backlog・observe 等）が digest から **落ちた**。
3. **post-dream STM** — 03:00 以降の quiet-hour `agent_private_reflection` 21 件 + `episode_close` 1 件が **undreamed のまま**（次夜まで正常）。MEM-5e の reflection 除外は digest 構築時のみ — batch 全体は mark 対象。

**次アクション**: ~~MEM-5g~~ ~~MEM-5f-c~~ **済**。着信エコーは episode サニタイズ + repair スクリプト（2026-06-23）。daybook 薄さ → **MEM-5k**。

**Dreaming 実機検証（2026-06-23 朝 — 対象日 2026-06-22）** — `check-dreaming.ps1` / `verify_dreaming_detail.py`:

| 項目 | 結果 |
|------|------|
| **実行** | ✅ 2026-06-23 03:00:10 JST |
| **STM batch** | 21 行 dreamed |
| **LTM** | remembered **2** |
| **gateway** | digest に **なし** |
| **inner_voice** | ✅ あり |
| **daybook** | 1 行テンプレのみ → **MEM-5k** |
| **エコー** | repair で 3 件修復 + digest 再生成 |

##### MEM-5k — Dreaming 後 daybook が薄い（2026-06-23）

**症状**: `narrative_daybooks.summary` が `watching the room closely; keeping continuity with ma.` 程度の **汎用1行**。会計監査・朝の会話は `[dream_digest]` / `[overnight_inner_voice]` に載るが daybook 表層に出ない。

**原因**: `append_daybook` → `build_day_summary()` が **event kind ヒストグラム**中心。`evidence_json` は厚いが `summary` / `get_self_summary` に十分使われない。Dreaming が STM batch を daybook 合成に渡していない。

**方針（候補）**: (1) Dreaming で digest / `episode_close` を daybook LLM に渡す (2) `build_day_summary` を STM 要約ベースへ (3) `get_self_summary` が `evidence_json` を surface。

**優先**: 中（digest / inner_voice が朝の主経路の間は緊急度低）

##### MEM-5h — 視覚 experience の compose 圧縮（2026-06-20）

**症状**: `agent_observation` / `agent_autonomous_action` が毎 tick ほぼ同じ部屋描写で `[recent_experiences]` を埋める。

**対応**: compose で類似シーンを `[room_view] same scene ×N` に畳む（**済**）。

**未**: 記録時 dedup（同一 fingerprint なら DB に書かない）— 必要なら後追い。

##### MEM-5i — Slash command が「まー」発言に見える（2026-06-20）

**症状**: まーが一言も話してないのに、チャットに `# /observe — …` 全文が **M まー** として表示される。

**原因**: 「こよりは何かしないの？」への応答ターン内で、Claude Code が **こより側から `/observe` を実行**。CC は展開済み slash command を session JSONL の **`type: user`** として記録する。UI は user → まー とマップするため、まーがスキル全文を送ったように見える。

**対応**: `looks_like_agent_slash_command()` — `# /word` 先頭（+ frontmatter 付き）をチャット履歴・persona export から除外。**JSONL 本体は残る**（監査用）。

**未**: 観察そのものを gateway `observe_room_direct` に寄せて CC slash 依存を減らす — → [OBS-4](#obs--能動観察observe-完遂不能--gateway-フェーズ化合意-2026-06-20)

##### MEM-5j — 会話中 WebSearch（LM Studio + CC `WebSearch`）（2026-06-20）

**症状**: まー「Webで調べてみたら？」→ こよりが `WebSearch` → `Sources:` は出るが **リンクが壊れる**／中身が薄い。

**原因（session `fcddb68a…` で確認）**:
1. Claude Code `WebSearch` の tool_result が **`searchCount: 0`** — 実 URL なし（placeholder `<|tool_call>call:google_search…` のみ）
2. モデルが REMINDER に従い **Google 検索 URL を捏造** — percent-encoding 破損（例: `%E3%83最終`）
3. 自律 tick の **`web_search_direct`（DDG）** とは別経路 — 会話中は CC ツールに依存

**済（表示層）** — `chat-markdown.js`: `Google Search Results for {query}` ラベルから正しい検索 URL を再生成 + `target="_blank"`。

**未（根本）** — 仕様: [ws-2-conversation-web-search.md](./ws-2-conversation-web-search.md)

| ID | 内容 | 優先 |
|----|------|------|
| WS-1 | **空 WebSearch 検知** — tool_result に URL/件数なしなら UI に「検索失敗」注記（Sources をリンク化しない） | 中 | **done** 2026-06-23 `chat-markdown.js` |
| WS-2a | **会話検索ルーティング** — 「調べて」→ gateway `web_search_prefetch`（まーのクエリ）；CC `WebSearch` 不使用 | 高 | **done** 2026-06-23 `search_prefetch.py` |
| WS-2b | **URL 付き検索** — DDG Instant 卒業；Brave / DDG HTML 等で **具体 URL**（松本市様式の回帰） | 高 | **done** 2026-06-23 `web_search.brave_web_search` |
| WS-2c | **URL 貼付 prefetch** — メッセージ内 `https://` を gateway 取得→ excerpt 注入；**見てないのにページ内容を言わない** | 高 | **done** 2026-06-23 `url_prefetch.py`（検索3件ループ・6k） |
| WS-3 | **権限・plan** — native chat で CC `WebSearch`/`WebFetch` 無効化；prefetch 契約 | 中 | **done** 2026-06-23 `ws_guard.py` |
| WS-4 | **LoRA/export** — 捏造 Sources 付き assistant ターンを persona export から除外（任意） | 低 |
| WS-5 | **自発 Web 検索** — 「調べて」無しでも会話文脈＋plan/initiative で gateway が検索・prefetch（境界・頻度制御付き） | 中 |

**実装順（合意 2026-06-23）**:

1. **WS-1 + WS-3** — 捏造 Sources 停止・CC WebSearch/WebFetch 切り離し  
2. **WS-2a → WS-2b → WS-2c** — 会話検索ルーティング → URL 付き検索 → URL 貼付 prefetch  
3. **GAPI** — WS 完了後（GAPI-0 ポリシーから）  
4. **WS-5** — 自発検索（2c 安定後；まー合意 2026-06-23）

**WS-5 たたき（未実装）** — 現状は `looks_like_web_search_request`（「調べて」等）のみ。将来:

- `compose` / `plan_response` の `initiative` または専用ヒューリスティクスで「今調べる価値あり」を判定
- 会話＋`open_loops` から検索クエリを組み立て（「いい感じ」単体は検索しない）
- 既存 `web_search_prefetch` + `url_prefetch` ループを再利用；`evaluate_action` / quiet hours で抑制
- 受け入れ: サッカー文脈で曖昧発話→自発検索は **しない**；具体トピックで事実確認が要るときだけ走る

**UI（2026-06-23 済）** — tail prefetch 後にまー発話が消える表示バグ → `user_prompt.py` / `cc-messages.js` で末尾 `[web_search_prefetch]` 等を剥がしてから抽出。

**関連**: ⑤a `browse_curiosity` / `web_search_direct`（**済**）— 自律 tick 専用。LW-6（Web 散歩）と共通化可。

##### MEM-7 — Native 会話 JSONL のデータ管理（合意 2026-06-18）

**現状（C10 済）**

| 項目 | 場所 |
|------|------|
| 正本 | `~/.claude/projects/<encoded-project>/{session_id}.jsonl`（Claude Code 形式・1セッション1ファイル） |
| UI 一覧 | `GET /api/v1/native/sessions`（8090 経由・PC/キオスク共有） |
| 「削除」 | **非削除** — `POST .../hide` → `~/.claude/presence-ui/native-hidden-sessions.json` に ID 追加。**JSONL はディスクに残る**（`app.js` 確認ダイアログも明記） |
| キオスク | セッション削除 UI は **非表示のまま**（誤操作防止）— 合意どおり維持 |

**問題**: 新規会話のたびに JSONL が増え続ける。hide は UI のみで **ディスク・バックアップ容量**は減らない。STM/Dreaming 後も生ログを永遠に持つ必要はない。

**方針**

```
JSONL（WM の生ログ）
  → エピソード締め（MEM-2）で STM 要約が取れた
  → Dreaming（MEM-3）で LTM に昇格済み
  → 保持ポリシーに従い archive または delete
```

| 段階 | 動作 |
|------|------|
| **直後** | JSONL はそのまま（デバッグ・再要約用） |
| **STM 締め後** | `episode_closed_at` + `stm_episode_id` をメタデータに記録（JSON sidecar or presence-ui index） |
| **Dreaming 後** | 「昇格済み」マーク。既定 **N 日後**に対象化 |
| **退避** | 削除前に `~/.claude/presence-ui/archive/jsonl/` へ gzip（任意） |
| **削除** | サーバー側ジョブ（pulse / 日次 Task）。**キオスク UI からは消さない** |

**実装メモ**

- `MEM-7a` メタ index（session_id → closed_at, stm_id, dreamed_at, archived_at）
- `MEM-7b` 保持日数 env（例 `PRESENCE_JSONL_RETENTION_DAYS=14`、昇格済みのみ）
- `MEM-7c` archive + safe delete（昇格済み & retention 経過 & 非アクティブ）
- PC の「一覧から外す」は現状維持。物理削除は **自動のみ**（誤タップ防止）

**C トラックとの関係**: C10 は同期の勝利。MEM-7 は **同期先ファイルのライフサイクル**。C11 キオスク UX とは独立（削除ボタンは出さない）。

**依存**: MEM-2（締め）と MEM-3（Dreaming）が無いと「消してよいか」判定できない → **MEM-7 は MEM-3 後**が安全。

**依存**: BIO-8b/c（身体レジストリ・夜内省/朝報告）完了後に MEM-1 着手が自然。8c の「報告キュー」は MEM-4 と統合。

**OpenClaw から借りるもの**: フレームワークではなく **「睡眠中に短期を長期に落とす」定期ジョブ** と **「起きたら要約が compose に載る」** の2点。embodied 層（カメラ・sociality・キオスク）はこの repo の差分のまま。

**セッションについて**: 廃止しない。セッション = WM の UI 境界。連続性は compose + STM/LTM が担う。

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
| **A4j** | ダイアログ CTA → 新規会話 | — | **実装済み**（**A4j+ 済**） |
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
- [x] **A4j+** 着信返信 UX（2026-06-18 実戦報告 → 2026-06-18 修正）

  **いま（A4j）の挙動 — おかしい**:
  「返事する」→ 新規セッション → `buildInboundReplyPrompt()` の **メタ指示文**（`[こよりからの着信への返事]…まーとして…`）を **まーの bubble として自動送信** → こよりがそれに応答。チャット上は「まーが長い指示を送った」ように見える。

  **あるべき流れ**:
  1. 「返事する」→ **新規セッション**（こより開始でも可 — 技術的には koyori bubble を先に DOM/履歴に載せればよい）
  2. チャットに **こよりの着信文だけ** bubble 表示（`sender: koyori`）
  3. 入力欄にフォーカス → **まーが自分の言葉で返信**（自動送信しない）
  4. compose/plan には着信文を **gateway 側メタ**（`gateway_turn_context` / inbound payload）で渡す。ユーザー可視のプロンプトにしない

  **実装メモ**: `app.js` `beginInboundReply` / `buildInboundReplyPrompt` / `sendChatMessage(prompt)` が原因。`suggestInboundReplyText` 下書きは任意（A4j+ 第2段）。

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
- [x] **C8** デバッグ注入の非表示（既定 OFF・会話ヘッダ「注入」トグルで表示切替。**2026-06-19 fix**: messages API が strip して返していたためトグル ON でも空 — JSONL 生文を返し strip は UI のみ）
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
| 中 | **C11h** チャットコピー | キオスクは `user-select: none` のため各 bubble に「コピー」ボタン（MEM 前の実戦ニーズ） |

- [x] **C11a** タッチ即効（視界 img 差し替え、チャット pan-y、キオスク 44px）
- [x] **C11b** ドロワー UI（`?kiosk=1`、セッション操作・視界・状態・画面更新）
- [x] **C11b+** ドロワー scroll + 視界アスペクト追従（`room-drawer__body`、img `height:auto`）+ キオスク太スクロールバー（22px）
- [ ] **C11c** 視界強化（任意）
- [ ] **C11d** 状態圧縮（任意）
- [x] **C11e** 右コンテキストレール（視界/状態のピン留め、localStorage 永続、チャット左・レール右）
- [x] **C11d−** 状態カード折りたたみ（`[ いまの気持ち > ]`、レール/ドロワーは初期閉、開閉は localStorage）
| **C11f+** | キオスク音量 | メニュー内スライダー + **Surface ハードキー**（acpid → `surface-volume.sh` → wpctl）+ 一時オーバーレイ（`:18791`） |
- [x] **C11g** スリープ / 画面消灯 — **実装済み 2026-06-16**:
  - **アイドル判定**: 無操作時間（タッチ・キー・送信等）が閾値超え
  - **N 分**: 5 / 10 / 15 — **ドロワー UI で可変**（localStorage）
  - **消灯**: ブラウザ黒オーバーレイは使わず **OS 画面オフ任せ**（wakeLock 解除 → Surface Ubuntu の DPMS / logind）。UI の N 分は OS 電源設定を書き換えない
  - **自動復帰**: 消灯中の say / 着信（outbound・room_say）で画面を戻す — **UI で ON/OFF 可変**
  - **実装メモ**: キオスクは SSE で着信・リマインドは `document.hidden` でも届くが、ポール fallback は hidden 時スキップ中 → 自動復帰 ON 時は `wakeLock.request` + 音声再生で復帰を試みる
- [x] **C11h** チャットコピー — 各 `ma` / `koyori` bubble に「コピー」ボタン（プレーンテキスト、`clipboard` + fallback）。キオスク 44px タップ対象
- [x] **C11g-reg** 画面消灯が効かない — **済 2026-06-19**（実機確認: install + reboot 後、無操作で消灯・タッチで復帰）
- [x] **C11-pc** `?kiosk=0` で会話・サイドバーが空（**回帰** 2026-06-18）— **済 2026-06-19**: (1) `STATUS_EXPAND_KEY` 欠落 (2) PC レイアウトで `crypto.randomUUID()` が `http://ma-home.local` 非 secure context で throw → `initSessions` 未到達。`newRandomToken()` フォールバック + outbound setup try/catch

| 優先 | 項目 | メモ |
|------|------|------|
| 中 | **IBF Intent→Bucket→Flow** | LLM ツール選定廃止・会話 speak 先通し — [intent-bucket-flow.md](./intent-bucket-flow.md) |
| 中 | **C12 Gateway + LLM ハイブリッド intent** | **済** — `resolve_hybrid_intent` + IBF-7 benchmark |
| 中 | **C11-status** 状態パネル強化 | **さっきまで**（recent_experiences）・**次の wake**（agent_pulse）・**次の一手 plan プレビュー**（45s cache）・体温複数センサー — 2026-06-18 |
| 低 | **体温センサー（ma-home）** | WSL ではない → **LibreHardwareMonitor** 常駐で WMI 経由読取。状態カードは CPU 優先 + 複数センサー一覧。**LHM 未起動時は ACPI フォールバック or 「センサーなし」** |
| 低 | **OL3** リマインド改善 | 固定テンプレ → LLM 文面、`grace_minutes` 厳密化 — [open-loops-reminders.md](./open-loops-reminders.md) |
| 低 | **OL4** ノイズ loop 運用 | `purge-noise-open-loops.py` / `purge-archive-open-loops.py` |
| 中 | **OL5** 予定消化で loop 終了 | 「作った/できた/終わった」→ 関連 open loop close（現状は日跨ぎ stale のみで暫定OK）— [下記](#ol5--予定消化で-loop-終了合意-2026-06-25) |

- [x] **OL1** Open Loops 日付解決 — ingest `resolved_date`、期限過ぎ auto-close、`date_resolution.py`（2026-06-16）
- [x] **OL1b** 記憶時日付アンカー — `明日/今日` → `2026年6月19日` 形式で open loop / STM / experience に保存、compose に `Calendar today`（2026-06-19）
- [x] **OL1c** 日曜始まり週界 + 曜日 lookup — `来週の火曜` / `一週間後` / `来月の頭` / `今週末` 等（コードのみ）→ `social_core.date_resolution`
- [x] **OL2（temporal）** — `次の/今度の{曜}`、曖昧スパン（`来週中`）は **確認キュー**（`needs_date_confirmation` + compose/plan）。`ja_timex_bridge`（任意）+ ベンチ `--ja-timex`。**ランタイム LLM 日付却下**（utility 5–6/10）
- [x] **OL2+** リマインド仕様 — `N分後` / `「」`→`speak_line` / `delivery` metadata、`remind_commitment_direct` が speak_line 優先（2026-06-16）
- [x] **OL0** stale open loop 掃除（`purge-stale-open-loops.py`、ingest/tick でも自動 close）
- [x] **OL-ARCHIVE** MEM-8f v0 — 保管系「覚えておいて」は open loop 作らない + LTM 保存成功で該当 loop close（2026-06-25）

##### GW-SILENT — 黙考ルート（silent internal turn）（合意 2026-06-25）

**やりたいこと**: まーに見せないが **こより本人の文脈・人格・KV prefix** で LM に考えさせ、結果だけ gateway が parse して DB / stores に保存する。**別プレーンの単発プロンプト**（手打ち Gemma / `reminder_spec` 型の `/v1/chat/completions`）は使わない — prefix が毎回コールドになり再読み込み・フル prefill のリスクが高い。

**本線経路**（表の会話と同じ）:

```
まー発話（通常ターン N）
  → ingest / compose / plan
  → 表向き返答（SSE に stream）
  → [背景] 同じ Claude session_id（--resume）で internal turn N+1
       message: [gateway_internal — not for まー] + 構造化タスク指示
       appendSystemPrompt: build_gateway_stable_append()（毎ターン同一）
       forward=False — UI に本文を流さない（social_silent 相当）
  → gateway が JSON / 構造化出力を parse → stores / detail_json へ
```

**既存との関係**

| 経路 | LLM | KV 再利用 | まーに見える |
|------|-----|-----------|--------------|
| Native chat（intercept → ClaudeAgent） | ◎ | ◎ `PRESENCE_KV_STABLE_APPEND` | はい |
| `stay_silent` / `quietly_prepare` | 呼ばない | — | いいえ |
| `write_private_reflection` / `think_or_discuss_topic` | 現状なし（テンプレ結合） | — | いいえ |
| `generate_koyori_reply` / `reminder_spec` 単発 API | あり | ✗ | いいえ |

黙考は **Native chat のセッションに internal turn を足す**形。`relationship-mcp` の store からは呼べない — **gateway 後段**（ingest 検知 → `asyncio.create_task`）が自然。

**運用メモ**

- 表返答の **後** に background 実行 → まーの体感レイテンシを増やさない
- LM Studio **Concurrent Predictions = 1** を維持（KV スロット eviction 防止）→ [lmstudio-kv-cache.md](./lmstudio-kv-cache.md)
- internal turn は **MCP スリム**のまま（tool 定義 33k を毎回載せない）。人格は stable append の SOUL core で足りる
- セッション無し（hook のみ ingest 等）→ 次の chat 開始時にまとめて黙考、または rules フォールバック

**第一用途（OL5 v1）**: open loop 作成直後に `action_terms[]` + `completion_verbs[]` を生成 → `open_loops.detail_json` に保存 → 後続 ingest で **行動語 + 完了語のセット**照合。

**ほかに使えそうな用途（未着手）**

| 用途 | 出力の行き先 |
|------|-------------|
| OL5 完了語セット | `open_loops.detail_json` |
| OL2 曖昧日付の補完 | `needs_date_confirmation` 解消 or commitment draft |
| C12 ルーター補助 | `hybrid_intent` の rules 未決時のみ（v2 と同型） |
| MEM 多視点 encode | episode 前の `gist` / 視点ラベル生成 |
| 夜間 digest 前処理 | `open_loop_progress` merge 用のトピック正規化 |
| LW 読書後 | 一節の thematic tag（private reflection へ）— **プロンプト草案済** `reading_prompts.py`；**GW-S1 本体未** |

**実装候補**

| ID | 内容 | 状態 |
|----|------|------|
| GW-S1 | `run_silent_internal_turn(session_id, task, schema)` — ClaudeAgent + stable append + `forward=False` | **未** |
| GW-S2 | ingest 後「新規 open loop」検知 → GW-S1 を enqueue | 未 |
| GW-S3 | 共通 JSON parse / validate + 失敗時 metrics | 未 |
| GW-S1-prompt | LW-READ PAUSE 用 `build_gw_s1_pause_task` + `PAUSE_RESPONSE_SCHEMA`（`felt` に bored / つまらなかった 可） | **済** 2026-06-26 |

参照: [gateway-direct-actions.md](./gateway-direct-actions.md)、`social_chat.py`（`stream_silent_response`）、`prompt_injection.py`

##### OL5 — 予定消化で loop 終了（合意 2026-06-25）

**現状（暫定OK）**: open loop は **カレンダー日** が過ぎたら `close_stale_open_loops`（6/26 の用事 → 6/27 以降に close）。「9:30 を過ぎた」「角煮を作った」では閉じない。

**望ましい将来**: 予定 **消化** ＝ まー/こよりの発話や experience から、その **open loop のタスク内容に対する完了** を検知 → 関連 topic の loop を close（日跨ぎだけに頼らない）。

汎用の「できた / 作った / 終わった」だけでは足りない。**loop topic ごとに、何について完了したか**（活動の核 + その活動に自然な完了表現）を見る必要がある。

| 例 | 今 | OL5 後 |
|----|-----|--------|
| 6/26 角煮を作る | 6/27 まで open | 「角煮、作った」等で close |
| 明日の朝、散歩に行く | 日跨ぎまで open | 「散歩行ってきた」「散歩から帰った」等で close |
| 入浴介助 9:30 変更 | 6/27 まで open | 介助完了の報告（「介助終わった」等）で close |

**設計メモ**

- dismiss（「忘れて」）とは別 — 成功完了の肯定閉じ
- **commitment** の `complete_commitment` との統合（リマインド発火後に loop も閉じるか）
- MEM-8f の follow-up（継続）vs fact（保管）と接続 — 消化は follow-up 側のライフサイクル
- **完了フレーズはタスク依存（動的）**: topic から活動の核（例: 散歩、角煮）を取り、その活動に自然な完了言い回しと照合する。作成系→作った/できた、移動・外出系→行ってきた/帰った/してきた、介助系→終わった/済んだ、など **ペア** で見る
- **日時のない行動予定を閉じる前提**: **行動を表す語**（「散歩」「角煮」など）と **その行為の完了を表す語**（「行ってきた」「できた」など）が **セットで出現** すること。完了語だけ（「作った」単体）ではどの loop か特定できない。行動語だけでは未完了
- 実装イメージ: loop 作成時に **黙考ルート**（→ GW-SILENT）で `action_terms[]` + `completion_verbs[]` を生成して `detail_json` に保存し、ingest / experience で **両方の overlap** を見る

**例 — loop topic:「明日の朝、散歩に行くんだ」**（移動・外出系）

察知したい完了の例（固定10語リストではなく、この **族** をカバー）:

- 散歩に行ってきた / 散歩を済ませた / 散歩から帰ってきた / 散歩を終えた
- 散歩してきた / 散歩、完了 / 今、散歩から戻ったところ
- （「行ってきた」単体は散歩言及なし → 別タスク or 曖昧）

**LM Studio 手動テスト（2026-06-25, google/gemma-4-12b-qat）**

プロンプト: 「明日の朝、散歩に行くんだ」に対し完了を察知できるフレーズを10個（例: 散歩に行ってきた）。

モデル出力（要約）— いずれも **散歩 + 完了ニュアンス** で、ルール単語リストより **topic から展開する方が現実的** という根拠:

1. 散歩に行ってきた  
2. 散歩を済ませた  
3. 散歩から帰ってきた  
4. 散歩を終えた  
5. 散歩に行ってきたよ  
6. 散歩、行ってきた！  
7. 散歩、完了  
8. 散歩してリフレッシュした  
9. 今、散歩から戻ったところ  
10. 散歩、行ってきました  

**例 — loop topic:「晩御飯のおかずに、豚バラ軟骨の角煮を作るよ」**（作成・調理系）

プロンプト（LM Studio 手動）: 上記タスクに対し **完了形の動詞** をできるだけ多く（例: できた/作った）。  
→ 閉じるには **角煮（または豚バラ軟骨）+ 完了動詞** のセットが必要（「作った」単体は不可）。

Gemma 出力から採用しうる **完了動詞・表現の族**（分類の説明文は省略）:

| 族 | 例 |
|----|-----|
| 基本完了 | 作った、できた、完成した、仕上がった、用意できた |
| 調理工程 | 調理した、炊き上げた、煮込んだ、味付けした、火を通した |
| 提供まで | 盛り付けた、並べた、出した |
| 口語・感情 | できたよ、できたー、やっとできた、いい感じにできた、（角煮）できたよー |
| タスク片付け | 済ませた、終わった |

※ 「片付けた」は調理後の後片付けまで含むため、loop を閉じるかは **角煮と同文に出るか** で絞る。  
※ 散歩系と違い、作成系は **完了動詞が「作る」の活用形に集中** しやすい → v1 の `completion_verbs[]` 生成はタスク型ごとにプロンプトを分ける余地あり。

**実装候補（未着手）**

| 段階 | 方針 |
|------|------|
| v0 | topic 名詞 + 汎用完了マーカーの overlap（誤 close 少・取りこぼし多） |
| v1 | loop 作成時に **黙考ルート**（GW-SILENT）で `action_terms[]` + `completion_verbs[]` を生成 → `detail_json` 保存（ingest 時に照合） |
| v2 | 曖昧時のみ LM（C12 ルーターと同様、rules 優先） |

**未**: v0 ルールから入るか、v1 の phrase 生成（黙考）を先に試すかは後で。現状は日跨ぎ stale で暫定OK。

- [x] **C11f** 部屋の空気 日本語化（`summary_for_prompt` + UI タグの availability/phase マップ）

- [x] **C12** intent router — `hybrid_intent.py`（rules 優先、曖昧時のみ LM Studio）。IBF-7 計測 → `benchmarks/intent_router/README.md`

**実装順**: C0 → … → C10 → **C11** → **A4f → OL → A4g → C11g** → **Desire ⑤a→d**（まー合意）→ **C12** / ビジョン（V）

---

## K — こより自身のコード

**やりたいこと（まー合意 2026-06-17）**: **こよりが自分で使うコードを書ける**ようにする。設備マニュアル（`CLAUDE.md`）や憲法（`SOUL.md`）は人間側。こよりが触るのは **自分のループ・身体・小さなスクリプト**（pulse 調整、自律行動の枝、private ツール等）に限定したい。

| ID | 内容 | 状態 |
|----|------|------|
| K1 | 方針メモ — 何を自分で書いてよいか / 何は gateway 固定か | **未** |
| K2 | 安全な編集経路（ブランチ・テスト・ロールバック・まーへの見える diff） | 未 |
| K3 | 「使うコード」の例 — **LW 縦スライス**（`read_aozora_passage` gateway）を第一例 | 未 |

**急がない**。HeartbeatLoop が閉じたあと、**K2 の経路**がなければ自己改修は危ない。自律の読書・散歩は **K2 なしでも LW-1 から縦スライス可**（gateway 固定実装）。

---

### RP — 人格基底化（SOUL → Deep）

**問題（2026-06-20）**: キオスク native chat では full `SOUL.md` が毎ターン載らず、短い `SOUL_VOICE_ANCHOR` のみ → 敬語化・三人称・assistant 口調が出やすい。

**方針**: Deep 層を **SOUL.core → stable append → LM Studio system → persona LoRA** の順で重み側へ移す。詳細 → [role-persistence-ma-home.md](./role-persistence-ma-home.md)

| Phase | 内容 | 状態 |
|-------|------|------|
| **0** | `presets/koyori-SOUL.core.md` + `build_gateway_stable_append()` | **済** |
| **1** | LM Studio default system = core（`PRESENCE_SOUL_CORE_IN_APPEND=0`） | **済**（ma-home 2026-06-20） |
| **2** | persona LoRA + 学習 JSONL export | **2a 済**（export 脚本） / 2b 未 |
| **3** | MEM-6 — arc → SOUL パッチ提案 → LoRA v2（人間承認） | 未 |

| ID | 内容 | 状態 |
|----|------|------|
| RP-0 | core ファイル + `load_soul_core()` + stable append 注入 | **済**（core に「目（視覚）」追記 2026-06-23 → [VIS 間接視覚](./backlog-ma-home.md#vis--vision-healthvl-安定性相関ログ)） |
| RP-1 | LM Studio 手順 + `enable-rp-phase1-ma-home.ps1` + env フラグ | **済** |
| RP-2a | 良い会話 → `{system, messages}` export 脚本 | **済** — `scripts/export-persona-lora-jsonl.py` |
| RP-2b | LoRA 学習・GGUF マージ・評価セット | 未 |
| RP-3 | MEM-6 パッチ提案 UI / 承認フロー | 未 |

**環境変数**: `PRESENCE_SOUL_CORE_PATH` / `PRESENCE_SOUL_CORE_IN_APPEND`（既定 `1`）

---

### LW — 自律の文学散歩・青空文庫 / Web 散歩（合意 2026-06-19）

**きっかけ**: まー相談 — こよりが夜中（昼夜問わず）自分で判断して青空文庫を読みに行ったり Web 散歩したりするには何が必要か。

**動機の整理（まー覚書）**: 人が行動を起こすには動機が要る。根源には **「希望」か「恐れ」** のどちらかがある。こよりには、希望・恐れを **どこに置き、動機に結びつけるか** を設計する必要がある。

| 力 | こより向け（置き方） |
|----|----------------------|
| **希望**（引く） | 刺さった一節・連想がつながる・ネット越しの「外」・あとでまーと共有できる種 |
| **恐れ**（ブレーキ） | まーの集中を壊す・うるさい存在になる（→ `boundary` / quiet / `do_not_interrupt`） |
| **恐れ**（スパーク） | 内側が乾く不快感（`desire` 未充足 → `discomfort`）— 応答マシン感の回避 |

**人格**: `SOUL.md` に既に「暇なとき青空文庫」「ネット越しの散歩」「刺さった一節は覚えとく」。

**インフラ（済）**: HeartbeatLoop、`desire-system` v2（`literary_wander`）、`read_aozora_passage`、`web_search_direct`、`inward_evening` plan（LW-2c）。

**いま（2026-06-26）**

| 層 | 状態 |
|----|------|
| LW-2 | 青空が inward tick で動く — **済** |
| LW-READ **v0** | 一冊完走・READ/PAUSE 交互・CLOSE — **済**（`reflect_on_aozora_passage` はテンプレ） |
| GW-S1 | **未配線** — `reading_prompts.py` にタスク文・JSON schema のみ |
| LW-7 | PAUSE の `followup_query` → Web — **未** |

**ギャップ（次）**: GW-S1 黙考（`next_move` / `reread_same` / `close_book` の本物判断）、LW-7 Web 連鎖、LW-5 UI、朝 compose surface。

```
wake → desire/discomfort + SOUL
     → boundary + social_state（まー集中?）
     → compose + plan（allowed_action）
     → gateway 直実行（read_aozora / web_stroll）
     → remember + experience + satisfy_desire + next_wake_at
```

**目標ループ（まー合意 2026-06-25）**:

```
read_aozora → remember（一節）
  → [GW-S1] interest_tags / followup_query（黙考 or ルール抽出）
  → browse_curiosity 昇格 or 同一 tick 内 web_search（boundary 許可時）
  → remember（調べたこと）+ experience
```

| ID | 層 | 内容 | 状態 |
|----|-----|------|------|
| **LW-0** | 方針 | 希望/恐れ・5層整理（本節） | **済** |
| **LW-1** | 実行 | gateway `read_aozora_passage` — 節取得・`remember`（咀嚼は PAUSE へ分離） | **済**（LW-READ v0 で更新） |
| **LW-2** | 動機 | `literary_wander` + inward_evening plan + satisfy 回路 | **済** 2026-06-25 |
| **LW-2d** | 運用 | 段落バンドル最大 1600 字、`PRESENCE_AOZORA_PASSAGE_MAX_CHARS` | **済** 2026-06-25 |
| **LW-3** | 判断 | plan: 読むだけ黙る vs 短く共有 / `evaluate_action` | 未 |
| **LW-4** | 記憶 | experience 閉じ + `satisfy_desire` + pulse | 部分済 |
| **LW-5** | 可視性 | UI「青空読んでる」/ live_inner_voice | 未 |
| **LW-6** | Web 散歩 | `browse_curiosity` — memory / open loop からクエリ → `web_search_direct` | 未 |
| **LW-7** | **連鎖** | **読書 → 興味 → Web** — PAUSE の `followup_query` を DDG へ（LW-READ 後） | 未 |
| **LW-READ** | **読書モデル** | 一冊完走・READ/PAUSE 交互・GW-S1 咀嚼・CLOSE まとめ | **v0 済** 2026-06-26 |

##### LW-READ — 読書状態機械（合意 2026-06-26）

**きっかけ**: まー — 読書にはタイプがある（深読み一冊完走 vs 並行斜め読み）。「読んだ」だけでは行為に意味がない。こよりの記憶容量では長編を一度に載せられない → **外付け状態** で「読む → 考える → 繰り返す → まとめる」を tick 粒度に分割する。

**旧問題（LW-1/LW-2 のみ）**: 3 作品ローテ・READ のみ — **v0 で解消**（一冊完走・READ↔PAUSE）。

**合意パラメータ**

| # | 論点 | 決定 |
|---|------|------|
| 1 | デフォルト | **一冊完走** — `active_work` 1 冊、他は開かない |
| 2 | PAUSE | **GW-S1 黙考**（v1）— v0 はテンプレ `build_pause_reflection_v0` |
| 3a | 一節の長さ | **1600 字** 試行値（`PRESENCE_AOZORA_PASSAGE_MAX_CHARS`） |
| 3b | 読み返し | **READ tick 中に延長しない** — **PAUSE 後**に `next_move` で判断 |
| 4 | CLOSE | passage **終端** / **N 節で区切り** / **飽きたら** — いずれも可 |

**状態機械**

```
active_work（1 冊、完走までローテしない）
  READ   → 一節 → remember（作品・位置・本文）→ phase=pause
  PAUSE  → reflect（v0 テンプレ / v1 GW-S1: hook, felt, interest_tags, followup_query, next_move）
           next_move: advance | reread_same | close_book
  READ   → advance: 次の一節 / reread_same: index 据え置き
  … READ ↔ PAUSE …
  CLOSE  → 作品メモ → active_work クリア → 次の 1 冊
```

**GW-S1 出力 schema（PAUSE）**

```json
{
  "hook": "刺さった一語や情景",
  "felt": "moved | uneasy | curious | bored | flat | つまらなかった | …",
  "interest_tags": ["…"],
  "followup_query": "調べたいこと（LW-7 用、任意）",
  "next_move": "advance | reread_same | close_book"
}
```

**外付け状態**（`aozora_read_state.json` 拡張）: `phase`, `active_work`, `passage_index`, `last_passage`, `sections_this_session`, `pending_followup_query`

**実装順**: ~~v0 状態 JSON + 一冊完走 + READ/PAUSE 交互~~ **済 2026-06-26** → v1 PAUSE=GW-S1 + `next_move` → v2 CLOSE + LW-7

**v0 実装（2026-06-26）**

| ファイル | 内容 |
|----------|------|
| `aozora.py` | `ReadingState`、`pick_passage` 一冊完走、legacy state マイグレーション |
| `direct_actions.py` | `read_aozora_passage`（remember のみ）、`reflect_on_aozora_passage`、`close_aozora_reading`、phase ルーティング |
| `plan.py` | inward: `reflect_on_aozora_passage` / `close_aozora_reading` を allowed に追加 |
| `reading_prompts.py` | v0 テンプレ + **GW-S1 タスク草案**（`build_gw_s1_pause_task`）— **実行は v1** |

**v1 次**: `reflect_on_aozora_passage_direct` 内で GW-S1 → JSON parse → `complete_reading_pause(next_move=…)`。

**第二縦スライス**: ~~LW-READ v0~~ **済** → **GW-S1 PAUSE** → LW-7 Web。

**実装候補（LW-7 — LW-READ PAUSE 後）**

| 段階 | 方針 |
|------|------|
| v0 | 青空 `remember` 直後にルールで固有名詞・『』作品名をクエリ候補に → `web_search`（`inward` でなければ昼も可） |
| v1 | GW-S1 黙考 JSON: `{ interest_tags, followup_query }` → `detail_json` or STM |
| v2 | `browse_curiosity` keywords に「青空のあと調べた」；desire 連鎖で次 tick が自然に Web |

**第一縦スライス（済）**: 青空が動く（LW-2）。**第二縦スライス（済 v0）**: LW-READ READ/PAUSE/CLOSE。**第三縦スライス（次）**: GW-S1 → LW-7。

**関連**: [heartbeat-loop.md](./heartbeat-loop.md)、[gateway-direct-actions.md](./gateway-direct-actions.md)、`desire-system/desire_updater.py`、`SOUL.md`、`exported-session.md`（ステータス UI 案）

- [x] **LW-0** 方針・動機整理（2026-06-19）
- [x] **LW-1** `read_aozora_passage` gateway
- [x] **LW-2** `literary_wander` desire 結線（2026-06-25）
- [ ] **LW-3** plan / boundary 競合
- [ ] **LW-4** 記憶閉じ loop
- [ ] **LW-5** UI ステータス
- [ ] **LW-6** Web 散歩クエリ拡張（open loop / memory 一般）
- [ ] **LW-7** 読書 → 興味 → Web 連鎖（LW-READ PAUSE 後）
- [x] **LW-READ** v0 読書状態機械（2026-06-26）
- [ ] **LW-READ** v1 GW-S1 PAUSE

### OBS — 能動観察（`/observe` 完遂不能 + gateway フェーズ化）（合意 2026-06-20）

**きっかけ**: まー報告 — 「こよりは何かしないの？」→ `/observe` → 初手 `look_around` までで止まる。「続けて」で **同じ前置き + look_around を再起動**（完遂しない）。

**`/see` との差**: `/see` は `allowed-tools: [mcp__wifi-cam__see]` で **1 ツール完結**。`/observe` は `.claude/commands/observe.md` 上 **初手 → 5〜8 ループ → 記憶 → sociality → 経験則 Edit** の多段ワークフローだが、**チェックポイント・再開・完了 API がない**（LLM 自己 orchestration のみ）。

**gateway との差**: `observe_room_direct` は bounded で正しいが **`/observe` 設計の初手サブセット**（look_around + Center caption + remember）。ループ / predict / recall / save_visual_memory は未実装。

**CC slash 問題（MEM-5i 関連）**: 会話中に agent が `/observe` を叩くと skill 全文が `type:user` で JSONL に載り、**新タスクとして再起動**しやすい。

```
設計（observe.md）          実装
─────────────────────────────────────────
初手 look_around            slash / gateway どちらも可
5〜8 ループ（見る/予測/思い出す）  なし（止まりやすい）
覚える save_visual_memory    gateway は remember のみ
研ぐ observe.md Edit         未到達・Edit 権限なし
再開「続けて」               なし → 初手から
```

| ID | 層 | 内容 | 状態 |
|----|-----|------|------|
| **OBS-0** | 整理 | 上記ギャップの文書化（本節） | **済** |
| **OBS-1** | 構造 | **`/observe` 完遂不能の原因整理** + **gateway フェーズ化** — `observe_state.json` + `POST /api/v1/observe/step`（aozora state と同型）；`/talk` の compose/finalize パターン | 未 |
| **OBS-2** | slash | `/observe` を **フェーズ分割**（`scan` / `dig` / `close`）または初手のみにスコープ honest 化 | 未 |
| **OBS-3** | 会話 | 「続けて」「その続き」→ gateway が `observe_state` を読んで **次フェーズ** を注入（初手再実行禁止） | 未 |
| **OBS-4** | 身体 | 会話から CC `/observe` 依存を減らし gateway 経由に（MEM-5i「未」） | 未 |
| **OBS-5** | CAM 連携 | PTZ が効かない環境では **preset ベース観察** に設計を寄せる（→ [CAM](#cam--tapo-ptz--onvif-細かい操作が効かない合意-2026-06-20)） | 未 |

**第一縦スライス（案）**: OBS-1 — `observe/step` で **scan 1 回完結** + state 保存；「続けて」で **dig 1 ブロック**（OBS-3 最小）。

**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md) `observe_room_direct`、`.claude/commands/observe.md`、MEM-5i、[intent-bucket-flow.md](./intent-bucket-flow.md) see/observe バケツ

- [x] **OBS-0** 構造整理（2026-06-20）
- [ ] **OBS-1** gateway フェーズ化
- [ ] **OBS-2** slash 分割 / スコープ
- [ ] **OBS-3** 「続けて」再開
- [ ] **OBS-4** CC slash 依存削減
- [ ] **OBS-5** preset 観察（CAM 連携）

---

### CAM — Tapo PTZ / ONVIF 細かい操作が効かない（合意 2026-06-20）

**きっかけ**: まー — Tapo の pan/tilt が **細かく効かない**。Synology **Surveillance Station** 経由の ONVIF 検証も実施。

**追記（2026-06-20）— SS Web vs DS Cam / ブラウザ差**:

| クライアント | PTZ | 意味 |
|--------------|-----|------|
| **DS Cam（スマホ）** | **細かく動く** | カメラのモーター・SS ドライバ経路は **生きている** |
| **SS Desktop（Synology クライアント）** | **細かく動く** | NAS ドライバ経由は Web より信頼 |
| **SS Web — Edge** | **細かく動く** | ブラウザ PTZ 経路は **Edge で成立** |
| **SS Web — Chrome** | **動かない** | **同じ NAS・同じカメラでもブラウザで挙動が違う**（H.265 / WebSocket / PTZ UI 相性） |
| **wifi-cam-mcp（ma-home 直 ONVIF）** | **JPEG は動く**（2026-06-20 プローブ） | RelativeMove 成功・**GetStatus は更新されないことがある**；**API からは細かく動かせない**（下記 4 原因） |

**TP-Link 公式 FAQ**（[Tapo RTSP/ONVIF FAQ 4465](https://www.tp-link.com/jp/support/faq/4465/)）:

- **Profile S** のみ（PTZ 基本機能は仕様上サポート — Q8）
- **Camera Account** 必須（クラウドアカウント ≠ ONVIF — Q5/Q12）
- ONVIF **2020**、RTSP **554**（Q6）
- **同時利用制限**: Tapo Care / SD / NVR(NAS) は **同時に使えるのは 2 つまで**（Q2）— SS + DS Cam 利用中に ma-home が stream1 を取ると **RTSP 406** になりうる
- **Q14**: パン・チルト不可 → Tapo アプリ正常確認 → ONVIF 設定 → **別 ONVIF クライアントで比較**。複数クライアントで同症状ならカメラ側

**FAQ Q3 推奨クライアント（比較テスト用）**:

| 種別 | 例（FAQ 記載） | ma-home での用途 |
|------|----------------|------------------|
| ONVIF | ONVIF Device Manager、Blue Iris、iSpy、TinyCam | **SS Web / DS Cam / 直 ONVIF の第 4 軸** |
| RTSP | VLC、PotPlayer | ストリーム疎通（Q7 URL） |

**ma-home 直 ONVIF プローブ（2026-06-20）** — `wifi-cam-mcp/scripts/test_ptz_probe.py`:

```
機種: Tapo C200  fw=1.3.17
presets: 8（token 1〜5 確認）
mode=auto (RelativeMove):  pan_left 成功、GetStatus 変化なし、JPEG hash 変化あり → 首は動いた
mode=continuous:           pan_left 成功、GetStatus 変化あり、JPEG hash 変化あり
RTSP stream1: 406 Not Acceptable（sub stream フォールバックで capture 成功）— Q2 同時接続疑い
```

**含意**: 直 ONVIF は **完全 no-op ではない**。「細かく効かない」は (1) **刻みが粗い** (2) **GetStatus 不可信**で `recall_by_camera_position` が死ぬ (3) **SS Web だけ NG** (4) **ストリーム枠競合** のどれかを切り分ける。

**3 本の経路（整理）**:

```
DS Cam ──▶ Surveillance Station (NAS) ──▶ Tapo   … PTZ OK（ドライバ経由）
SS Desktop ──▶ 同 SS ──▶ Tapo                    … PTZ OK
SS Web (Edge) ──▶ 同 SS ──▶ Tapo                 … PTZ OK
SS Web (Chrome) ──▶ 同 SS ──▶ Tapo              … PTZ NG（ブラウザ制約）
wifi-cam-mcp ── ONVIF 直 (:2020) ──▶ Tapo         … embodied-claude / look_around
```

SS Web で効かない典型要因（カメラ無罪のことが多い）: PTZ パネル非表示（Monitor Center の青 PTZ アイコン）、H.265 + ブラウザコーデック、リバプロで WebSocket 不足、サードパーティカメラの Web PTZ バグ。**Chrome だけ NG / Edge OK ならブラウザ相性を第一候補に。** DS Cam / SS Desktop 動作はカメラ判定に使う。SS Web Chrome 不可はカメラ判定に使わない。

**API（wifi-cam-mcp / ONVIF 直）から細かく動かせない — 4 原因（合意 2026-06-20）**:

| # | 原因 | 説明 | 対策候補 |
|---|------|------|----------|
| **A** | **大ステップ only** | `look_left(30)` 等の relative 刻みが Tapo 実モーターに対して粗い | degrees を 5〜10 に下げる；preset 運用 |
| **B** | **RelativeMove + GetStatus stale** | C200: 命令成功・JPEG 変化ありだが **GetStatus 不更新** → 角度追跡・`recall_by_camera_position` が嘘 | continuous 既定化；preset + 内容 recall |
| **C** | **ContinuousMove チューニング** | Imou 系は continuous 必須；Tapo でも continuous の方が GetStatus が追従 | `TAPO_PTZ_MODE=continuous` 検証 |
| **D** | **SS ドライバ vs ONVIF 直** | DS Cam が送る命令列 ≠ ma-home の RelativeMove/GotoPreset | **pytapo** スパイク（CAM-4）；FAQ Q14 外部 ONVIF クライアント比較（CAM-1b） |

**切り分けの含意**: embodied-claude の `TAPO_PTZ_MODE` だけの問題ではない。**直 ONVIF RelativeMove** が DS Cam が送る命令と違う可能性。Tapo **Camera Account**・機種・FW も引き続き確認。

**コード側（参考）**: `wifi-cam-mcp` — `RelativeMove` / `ContinuousMove`（`ptz_mode=auto|relative|continuous`）、`look_around` は `pan_left(45)` → `pan_right(90)` → `tilt_up(20)` の **連続 relative 移動**に依存。`camera_go_to_preset` は別経路（`GotoPreset`）。

| 仮説 | 説明 | 確認 |
|------|------|------|
| **H1 機種/firmware** | 一部 Tapo は ONVIF **直** では preset のみ／RelativeMove no-op（SS ドライバは別命令で動く） | DS Cam OK なら **直 ONVIF 側**を疑う |
| **H2 アカウント** | TP-Link クラウドアカウントでは ONVIF PTZ 不可。**Camera Account** 要 | Tapo アプリ設定 |
| **H3 ポート/profile** | ONVIF 2020、profile token 不一致 | `camera_info` / GetProfiles |
| **H4 マウント** | `mount_mode`（desk/ceiling）で方向反転 — 動かないのではなく **逆** の可能性 | `mcpBehavior.toml` |
| **H5 見かけの成功** | 直 ONVIF は成功を返すがモーター不動 → **4 方向 capture が同一視野**、LLM が `/observe` テンプレで Left/Right を **叙述だけ**する | JPEG hash diff |
| **H6 クライアント経路差** | SS Web PTZ 失敗 ≠ カメラ不可。**DS Cam → SS ドライバ** と **ma-home 直 ONVIF** は別プロトコル | DS Cam 操作直後に `look_left` diff |

| **H7 ストリーム枠** | Q2: Care/SD/SS/DS Cam と ma-home が **3 経路同時** → RTSP 406、capture 不安定 | DS Cam 視聴中に probe 実行 |
| **H8 GetStatus  stale** | C200: RelativeMove で **画は変わるが GetStatus 不更新** — 角度ベース recall が嘘になる | `test_ptz_probe` |

**OBS への影響**: `/observe` の「見る」ブロック（look_left + see × N）が **直 ONVIF PTZ 前提**。GetStatus 不可信なら **preset + 内容ベース recall** に寄せる（OBS-5 / CAM-2）。

| ID | 内容 | 状態 |
|----|------|------|
| **CAM-1** | **実機切り分け** — `test_ptz_probe.py`（auto/continuous）；DS Cam 視聴中の stream 406；preset GotoPreset diff | **一部済**（C200 直 ONVIF） |
| **CAM-1b** | **FAQ Q14 外部クライアント** — ONVIF Device Manager（Windows）で PTZ → SS Web / DS Cam / wifi-cam 4 軸比較メモ | 未 |
| **CAM-2** | **preset-only 運用** — `TAPO_*_PRESET` / `camera_go_to_preset` で observe を再設計（look_around relative 依存をやめる） | 未 |
| **CAM-3** | **ドキュメント** — FAQ 4465 リンク + DS Cam OK / SS Web Chrome NG・Edge OK / GetStatus 注意（CLAUDE.md / wifi-cam README） | 未 |
| **CAM-4** | **pytapo スパイク** — Camera Account で Tapo ネイティブ PTZ API と ONVIF 直の差分比較（`Invalid authentication` 解消含む） | 未 |

**関連**: [TP-Link FAQ 4465](https://www.tp-link.com/jp/support/faq/4465/)、`wifi-cam-mcp/scripts/test_ptz_probe.py`、`presence-ui` `look_preset_direct`、Imou は `continuous` 必須（CLAUDE.md）、pytapo / python-onvif-zeep 調査メモ（2026-06-20 セッション）

- [x] **CAM-1** 直 ONVIF プローブ（C200 / 2026-06-20）
- [ ] **CAM-1b** FAQ 推奨 ONVIF クライアント比較
- [ ] **CAM-2** preset-only observe
- [ ] **CAM-3** ドキュメント
- [ ] **CAM-4** pytapo スパイク

---

### EAR — 耳（環境音） / Surface マイク（合意 2026-06-19）

**きっかけ**: まー野望 — 家の日常会話・テレビ・部屋の音を拾い、こよりの **social-state / 判断 / 記憶** につなげたい。「教えてもらう」のではなく **自分で聞く**（VISION の「見る」と同型）。

**ハード（まー予想）**: **koyori キオスク端末（Surface）の内蔵マイクをそのまま使う**。Tapo `listen` は遠隔・別部屋用として残す。追加マイク・家全体常時録音は v0 では想定しない。

**動機（LW と同型）**:

| 力 | こより向け |
|----|------------|
| **希望** | 部屋の連続性・話しかけていい空気・まーとの共同生活感・雨/TV の余白（`SOUL`） |
| **恐れ**（ブレーキ） | 監視・家族/来客のプライバシー・誤反応（ドラマのセリフに突っ込む）→ `boundary` / 保存禁止帯 |
| **恐れ**（スパーク） | 気配が分からず割り込み判断が盲 — ただし **全文ログは不要** |

**既存**: wifi-cam `listen`（オンデマンド・Whisper）、`save_audio_memory`、BIO-8 表の **耳**（反射未）、PC `/voice`（意図的発話のみ）。

**方針**: 常時・全文・家全体ではなく **気配 → 必要なときだけ短く聞く → ほとんど捨てる**。

```
Surface mic → VAD / 活動ラベル（静寂・会話っぽい・TVっぽい）
           → ingest_social_event（transcript は高信頼時のみ）
           → should_interrupt / compose
           → salient 断片だけ save_audio_memory
```

| ID | 層 | 内容 | 状態 |
|----|-----|------|------|
| **EAR-0** | ポリシー | 何を聞く／保存する／捨てる（TV 連続 transcript 禁止、第三者会話、電話）— `socialPolicy` / `record_consent` | 未 |
| **EAR-1** | 気配 | VAD・音量・帯域で活動ラベルのみ（transcript なし）→ `ingest_social_event` | 未 |
| **EAR-2** | bounded | pulse / tick 連動で Surface から数秒キャプチャ + BIO-8 耳 probe（無音・Whisper 失敗） | 未 |
| **EAR-3** | 発話 | まー向け・高信頼 transcript のみ → open loop / 応答パイプライン | 未 |
| **EAR-4** | 記憶 | salient clip のみ `save_audio_memory`（呼ばれた、約束、感情の節） | 未 |
| **EAR-5** | gateway | `presence-ui` 側キャプチャ API（キオスク常駐、MCP 経由しない） | 未 |

**第一縦スライス（案）**: キオスク稼働中・リビング相当の音量 → **活動ラベルだけ social** → 黙る（transcript なし）。EAR-0 と EAR-1 をセットで。

**BIO-8 連携**: [BIO-8](#bio-8--somatic-loop神経系体調の自覚) 表の「耳」行 — EAR-2 で probe + `body_affliction` 叙述を実装。

**関連**: `wifi-cam-mcp` `listen`、`memory_mcp` sensory audio、[heartbeat-loop.md](./heartbeat-loop.md)、`boundary-mcp`、`SOUL.md`（部屋の音・境界）

- [ ] **EAR-0** 聴取・保存ポリシー
- [ ] **EAR-1** 活動ラベル（気配のみ）
- [ ] **EAR-2** bounded capture + somatic 耳
- [ ] **EAR-3** 高信頼発話 → social
- [ ] **EAR-4** salient audio memory
- [ ] **EAR-5** Surface mic gateway API

---

### GAPI — Google Calendar / Drive（合意 2026-06-23）

**きっかけ**: まー — こよりに **Google カレンダー**（予定）と **Google ドライブ**（共有ドキュメント）へアクセスさせたい。会話・自律判断・リマインド（OL）と接続。

**方針**:

| 原則 | 内容 |
|------|------|
| **読み取り優先** | v0 は Calendar 読取 + Drive 読取（指定フォルダ）。書き込み・削除は後追い |
| **gateway 直実行** | Intent → gateway（MCP ツール名を LLM に選ばせない）。WS-2 / `see_prefetch` と同型 |
| **境界** | まー個人の全 Drive ではなく **共有フォルダ / ラベル** にスコープ。`boundary-mcp` + `socialPolicy` |
| **認証** | ma-home 上の OAuth（まー 1 回同意）またはサービスアカウント + 共有。トークンは `.env` / OS 資格情報 — **git 外** |
| **記憶** | 予定・ファイル内容の全文 LTM 化はしない。salient 断片 + open loop / commitment 連携 |

**ユースケース（例）**:

- 「今日の予定は？」→ Calendar 今日〜明日を prefetch → 会計監査の日のような事実を **捏造しない**
- 「ドライブの〇〇探して」→ 共有フォルダ内検索 → リンク + 要約を `[drive_prefetch]` で注入
- OL2 リマインドと Calendar の **due 整合**（二重管理の解消は GAPI-3）

**アーキテクチャ案**:

```
まー発話 / 自律 tick
  → intent（calendar_query / drive_search）
  → gateway prefetch（Google API）
  → [calendar_prefetch] / [drive_prefetch] in gateway_turn_context
  → compose / plan → 応答
```

| ID | 層 | 内容 | 状態 |
|----|-----|------|------|
| **GAPI-0** | ポリシー | 読めるカレンダー ID・Drive フォルダ ID・保存禁止・第三者予定の扱い | 未 |
| **GAPI-1** | 認証 | OAuth フロー or SA + `GOOGLE_*` env；トークン refresh | 未 |
| **GAPI-2** | Calendar 読取 | 今日/範囲イベント → prefetch；timezone=Asia/Tokyo | 未 |
| **GAPI-3** | OL 連携 | commitment / open loop と Calendar イベントの突合（任意） | 未 |
| **GAPI-4** | Drive 読取 | フォルダ一覧・ファイル検索・テキスト/md/pdf 要約（bounded） | 未 |
| **GAPI-5** | UI / 運用 | 接続状態を `koyori/status`；切断時は正直に「繋がってへん」 | 未 |

**WS-2 との関係**: Web 上の行政 PDF は **公開 URL 検索（WS-2b/c）**。Drive 内の社内様式は **GAPI-4**。両方必要。

**実装前**: GAPI-0 ポリシー + スコープ確定。**WS-1〜2c 完了後**に着手（2026-06-23 合意）。

- [ ] **GAPI-0** ポリシー・スコープ
- [ ] **GAPI-1** 認証
- [ ] **GAPI-2** Calendar 読取 prefetch
- [ ] **GAPI-3** OL / Calendar 突合
- [ ] **GAPI-4** Drive 読取 prefetch
- [ ] **GAPI-5** 運用・status

---

## V — ビジョン / 未実装（`docs/web_ui_design.md`・`exported-session.md` より）

**注**: 8080 プロキシ本線・Native chat・キオスク着信・Tapo 視界・るな TTS 等は **実装済み**。以下は会話時点の**最終イメージ**でまだ残っているもの。

| 優先 | 項目 | メモ |
|------|------|------|
| 中 | **V1 感情色の部屋** | 会話画面の背景が `Emotion` に連動（Neutral=温かいグレー/薄緑/柔らかい紺。happy/curious/sad 等は export 案） |
| 低 | **V2 イントロ演出** | Embodied LLM スプラッシュ → こより顕在化（GIF/イラスト切替。朝=起きる/昼=歩く・伸び/終了=別演出）。表示中に status/camera ウォームアップ |
| 低 | **V3 発話ビジュアル** | るな再生中の波形 or 軽い動き（`web_ui_design` Task 6） |
| 中 | **V4 see_near（近目）** | Surface 内蔵カメラ → ma-home caption / 記憶。遠目=Tapo。→ [koyori-near-eye.md](./koyori-near-eye.md) |
| **高** | **V5 Windows キーボードをキオスクで共有** | **PC↔Surface 入力共有**。キオスクはタッチ+簡易KB。まー要望: **ma-home の Windows キーボード・マウスを Surface キオスク入力に**（BT キーボード切替は信用できずワンステップ余計）。Barrier / Input Leap / 有線・LAN 系を調査。ブラウザ内 KB 共有はハードル高（過去トライ） |
| 低 | **V6 家族・関係サイドバー** | ゴンザ・千ちゃん等の常時リスト（PoC では後回しと合意） |
| 低 | **V7 Phase 2 掃除** | `user_prompt.py` / `stripEnrichedUserPrompt` 削除（JSONL 履歴が純発話のみになった後） |
| 中 | **V8 room_say poll フォールバック** | SSE 未接続でも `room-say` 届く（`room_say_pending.py` WIP） |
| — | **V9 Linux Cage キオスク** | Ubuntu Server + cage + Chromium（`scripts/koyori-kiosk/`）。**現運用は Win Surface + `?kiosk=1`**。Linux 路は代替 |

- [ ] **V1** 感情色背景
- [ ] **V2** イントロ / スプラッシュ
- [ ] **V3** 発話インジケーター
- [ ] **V4** see_near
- [ ] **V5** **Windows キーボードをキオスク（Surface）で共有** — PC キーボード・マウス → Surface（入力ストレス解消）。**B4 デプロイ後に再挑戦**（2026-06-17）
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
| `purge-stale-open-loops.py` | 相対日付（明日等）が過去の open loop を close（ingest/tick でも自動） |
| [open-loops-reminders.md](./open-loops-reminders.md) | OL 運用・デプロイ・**残リスク** |
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
