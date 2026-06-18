# ma-home / koyori バックログ

**最終更新**: 2026-06-18（BIO-8 完了、次トラック MEM）  
**方針**: こより本体（記憶・gateway 身体）は **様子見**。部屋 UI は **Native 会話エンジン + `/` の殻** を育てる（8080 プロキシ UI は投資しない）。

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

### 次の順（合意 2026-06-17・まー）

1. **B4** — 各 `install-*-task.ps1` を再実行して VBS ランチャーを Task に載せる（ログオン時の一瞬ターミナルを消す）
2. **V5** — PC↔Surface キーボード・マウス共有を再調査・再挑戦（Barrier / Input Leap / LAN 系）
3. **K1** — こより自身が使うコードを書ける経路を設計（急がないがバックログに置く）

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
| **MEM** | **記憶層・Dreaming** | セッション跨ぎ・短期→長期昇格（BIO-8 の次） | **未** → [MEM — 記憶層](#mem--記憶層セッション跨ぎ--dreaming) |
| **K** | **こより自身のコード** | 自分用の改修・小さな実装を自分で | **未** → [K1](#k--こより自身のコード) |

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

**残存**: 15 分 Task は `PRESENCE_PULSE_MAX_SEC` 超のセーフティネットとして維持。

**次の主トラック（合意 2026-06-18）**: **MEM**（記憶層・Dreaming）。セッションは廃止しないが、連続したこよりは **外部記憶の強化とシフト**で支える。

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

**手計算メモ（2026-06-18 `social.db`）**: `scripts/score-stm-entries.py --day 2026-06-18` で再現。

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
| 中 | **C11h** チャットコピー | キオスクは `user-select: none` のため各 bubble に「コピー」ボタン（MEM 前の実戦ニーズ） |

- [x] **C11a** タッチ即効（視界 img 差し替え、チャット pan-y、キオスク 44px）
- [x] **C11b** ドロワー UI（`?kiosk=1`、セッション操作・視界・状態・画面更新）
- [x] **C11b+** ドロワー scroll + 視界アスペクト追従（`room-drawer__body`、img `height:auto`）+ キオスク太スクロールバー（22px）
- [ ] **C11c** 視界強化（任意）
- [ ] **C11d** 状態圧縮（任意）
- [x] **C11e** 右コンテキストレール（視界/状態のピン留め、localStorage 永続、チャット左・レール右）
- [x] **C11d−** 状態カード折りたたみ（`[ いまの気持ち > ]`、レール/ドロワーは初期閉、開閉は localStorage）
- [x] **C11f+** キオスク音量スライダー — メニュー内 0–100%、localStorage、Aivis / Web Speech に適用
- [x] **C11g** スリープ / 画面消灯 — **実装済み 2026-06-16**:
  - **アイドル判定**: 無操作時間（タッチ・キー・送信等）が閾値超え
  - **N 分**: 5 / 10 / 15 — **ドロワー UI で可変**（localStorage）
  - **消灯**: ブラウザ黒オーバーレイは使わず **OS 画面オフ任せ**（wakeLock 解除 → Surface Ubuntu の DPMS / logind）。UI の N 分は OS 電源設定を書き換えない
  - **自動復帰**: 消灯中の say / 着信（outbound・room_say）で画面を戻す — **UI で ON/OFF 可変**
  - **実装メモ**: キオスクは SSE で着信・リマインドは `document.hidden` でも届くが、ポール fallback は hidden 時スキップ中 → 自動復帰 ON 時は `wakeLock.request` + 音声再生で復帰を試みる
- [x] **C11h** チャットコピー — 各 `ma` / `koyori` bubble に「コピー」ボタン（プレーンテキスト、`clipboard` + fallback）。キオスク 44px タップ対象
- [ ] **C11g-reg** 画面消灯が効かない — **修正 2026-06-19**: 原因は `koyori-kiosk.sh` の `xset -dpms`（DPMS 無効化）。`+dpms` + `koyori-screen-idle-server`（`:18790`）+ `app.js` から `screen-off` 呼び出し。Surface で `install-koyori-kiosk.sh` 再実行後リブート。任意: `KOYORI_CONSOLEBLANK_SEC=900` で GRUB `consoleblank`（[メモ](https://intinfinity.com/index.php/archives/1084)）
- [ ] **C11-pc** `?kiosk=0` で会話・サイドバーが空（**回帰** 2026-06-18）— ma-home ブラウザ（PC レイアウト）でチャット履歴・右レールが表示されない。`isKioskLayout()` と session マウント / native history ポールの分岐を確認

| 優先 | 項目 | メモ |
|------|------|------|
| 中 | **IBF Intent→Bucket→Flow** | LLM ツール選定廃止・会話 speak 先通し — [intent-bucket-flow.md](./intent-bucket-flow.md) |
| 中 | **C12 Gateway + LLM ハイブリッド intent** | **済** — `resolve_hybrid_intent` + IBF-7 benchmark |
| 中 | **C11-status** 状態パネル強化 | **さっきまで**（recent_experiences）・**次の wake**（agent_pulse）・**次の一手 plan プレビュー**（45s cache）・体温複数センサー — 2026-06-18 |
| 低 | **体温センサー（ma-home）** | WSL ではない → **LibreHardwareMonitor** 常駐で WMI 経由読取。状態カードは CPU 優先 + 複数センサー一覧。**LHM 未起動時は ACPI フォールバック or 「センサーなし」** |
| 低 | **OL3** リマインド改善 | 固定テンプレ → LLM 文面、`grace_minutes` 厳密化 — [open-loops-reminders.md](./open-loops-reminders.md) |
| 低 | **OL4** ノイズ loop 運用 | `purge-noise-open-loops.py` |

- [x] **OL1** Open Loops 日付解決 — ingest `resolved_date`、期限過ぎ auto-close、`date_resolution.py`（2026-06-16）
- [x] **OL2+** リマインド仕様 — `N分後` / `「」`→`speak_line` / `delivery` metadata、`remind_commitment_direct` が speak_line 優先（2026-06-16）
- [x] **OL0** stale open loop 掃除（`purge-stale-open-loops.py`、ingest/tick でも自動 close）

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
| K3 | 「使うコード」の例 — pulse ヒューリスティック、desire 反応、小さな gateway 拡張 | 未 |

**急がない**。HeartbeatLoop が閉じたあと、**K2 の経路**がなければ自己改修は危ない。

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
