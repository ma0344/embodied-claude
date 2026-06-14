# ma-home / koyori バックログ

**最終更新**: 2026-06-10（UI → Native 本線へ移行）  
**方針**: こより本体（記憶・gateway 身体）は **様子見**。部屋 UI は **Native 会話エンジン + `/` の殻** を育てる（8080 プロキシ UI は投資しない）。

**実行方針（合意 2026-06-14）**: 判断は compose/plan/stores のまま。**身体・自律の実行**は MCP に頼らず gateway 直実行へ（remember 直実行と同型）。詳細 → [gateway-direct-actions.md](./gateway-direct-actions.md)

あとでやること。完了したら `[x]` にするか「完了」セクションへ移す。

---

## 優先順（合意 2026-06-13 → **2026-06-14 更新**）

| 順 | トラック | 内容 | 状態 |
|----|---------|------|------|
| **D** | Backlog 最新化 | このファイルを現実に合わせる | **完了** |
| **B** | 運用自動化 | ログオン常駐・手起動を減らす | **ほぼ完了**（B2 LM Studio 手動のみ） |
| **A** | 記憶・魂・gateway 身体 | 本体 E2E + A3 直実行 | **様子見**（自動 PASS + 実戦 spot check 継続） |
| **C** | **部屋 UI（Native 本線）** | `/` 殻 + `/api/native/chat`、8080 脱却 | **次の主作業** |

**フェーズ判断（2026-06-14）**: 記憶 compose / vision prefetch / open loop dismiss / desire 注入は **8090 で実戦 OK**。大きな本体機能追加は止め、日常利用＋`verify-mission-a.ps1` で様子を見る。**TTS（`tts-mcp/.env`）は後回し**。

**UI と本体の兼ね合い**: ミッションA の「人間1ターン」は **CLI でも `:8090/` でも可**。本体変更時は `restart-presence-ui.ps1`（内部で `sync-presence-deps`）。

---

## 今どこにいるか（2026-06-14）

| 層 | 状態 |
|----|------|
| **記憶インフラ** | HTTP daemon `:18900` 常駐。compose recall・gateway remember **OK** |
| **Gateway `:8090`** | compose/plan + KV 安定注入。**身体は gateway 直実行済み**（see / observe / reflect / autonomous-tick）。vision prefetch + remember **実戦 OK**（窓・デスク・ダイニング） |
| **関係性** | open loop dismiss + commitment cancel。「覚えてる？」recall 誤 loop 抑制 |
| **表面 UI** | **Native 本線**（localStorage 会話・8080 取込 **完了 2026-06**） |
| **運用** | Task×4（memory / webui / presence / watchdog）+ post-logon-smoke **OK** |

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
| Claude Code Web UI | 8080 | `EmbodiedClaude-WebUI` | `install-webui-task.ps1` | `...\webui.log` | **C9 まで任意**（Native 会話は不要） |
| presence-ui | 8090 | `EmbodiedClaude-PresenceUI` | `install-presence-ui-task.ps1` | `...\presence-ui.log` |

**推奨登録順**（memory → presence-ui。Native 本線では **8080 は任意**）:

```powershell
cd C:\Users\ma\src\embodied-claude

.\scripts\install-memory-daemon-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-MemoryHTTP

.\scripts\install-webui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-WebUI

.\scripts\install-presence-ui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-PresenceUI
```

**再起動後チェック**（`post-logon-smoke.ps1` 一発）:

```powershell
.\scripts\post-logon-smoke.ps1
```

- [x] **B1b** 再起動後 `post-logon-smoke.ps1` — 2026-06-14 まー確認: Task×4 + 18900/8080/8090 OK（:18901 は Claude 起動まで未起動で正常）

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
- [ ] **A3c 運用** — `miss_companion` / natural tick TTS — **`tts-mcp/.env` 後回し**（合意 2026-06-14）
- [ ] **保存と想起の一貫性** — 窓・会議は spot check PASS 済み。「さっき見た」だけ memory 想起（再撮影なし）は任意改善
- [ ] **save_visual_memory HTTP** — MCP 完全 parity。急がない
- [ ] **Gemma `remember` 信頼性** — 観察のみ
- [ ] **初回 remember の遅さ** — 低優先（daemon 常駐で大部分解消）
- [x] **ミッションB/C**（欲求・体験・関係性）— compose `compact_prompt_block` に `[desires]` / `[open_loops]` / `[interpretation_shifts]` / `[recent_experiences]` 注入。plan は shift 本文を `must_include` に載せる（2026-06-14）

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
| 中 | **C7 画面構成・レイアウト** | 視界・ステータス・チャットの調整 |
| 低 | **C8 デバッグ注入の非表示** | `gateway_turn_context` / `vision_prefetch` をユーザーに見せない |
| 後回し | **C9 8080 Task optional 化** | `EmbodiedClaude-WebUI` を外せるように（smoke 更新） |

- [x] **C1** Native PoC 試験 — [docs/c1-native-poc.md](./c1-native-poc.md)（部分採用）
- [x] **C2** twicc 見送り — [docs/c2-twicc-decision.md](./c2-twicc-decision.md)
- [x] **C0** Native 既定 ON（`install-presence-ui-task.ps1` が初回 `presence-ui.local.env` を作成）
- [x] **C3** `/` チャット層 Native 化（`ui-config` + `app.js` SSE `/api/native/chat`）
- [x] **C4** セッション UI 再設計（localStorage 履歴・一覧・削除。8080 ワンショット取込 **完了** → UI 撤去）
- [x] **C5** キャンセル UI（「止める」ボタン + AbortController）
- [ ] **C6** Markdown 表示
- [ ] **C7** 画面構成・レイアウト
- [ ] **C8** デバッグ注入の非表示
- [ ] **C9** 8080 依存の緩和（運用・smoke）

**実装順**: C0 → C3 → C4 → C5 → C6/C7/C8 → C9

---

## Web UI / Surface（C3–C8 に統合）

旧 8080 前提の「セッション削除 UI」等は **C4/C5（Native セッション）** へ置き換え。

---

## 手動・デバッグ早見

| スクリプト | 用途 |
|-----------|------|
| `check-mcp-processes.ps1` | MCP / daemon / STALE 診断 |
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

**自律 tick**: `POST http://127.0.0.1:8090/api/v1/autonomous-tick` → [gateway-direct-actions.md](./gateway-direct-actions.md)

**前提**: LM Studio、`.claude/settings.local.json`、`.mcp.json`（memory は `uv run --no-sync`）
