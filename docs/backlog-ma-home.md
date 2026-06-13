# ma-home / koyori バックログ

あとでやること。完了したら行を消すか `[x]` にする。

## システム起動時: Claude Code Web UI + presence-ui を Daemon 常時起動

**やりたいこと**: Windows ログオン（システム起動後）に、脳（:8080）とこよりの部屋（:8090）を自動で立ち上げ、落ちたら再起動する。

**状態**: スクリプトは揃っている。**Scheduled Task の登録・再起動後の動作確認は未着手**。


| サービス               | ポート  | Scheduled Task              | Daemon                         | ログ                                                           |
| ------------------ | ---- | --------------------------- | ------------------------------ | ------------------------------------------------------------ |
| Claude Code Web UI | 8080 | `EmbodiedClaude-WebUI`      | `run-webui-ma-home-daemon.ps1` | `%USERPROFILE%\.config\embodied-claude\logs\webui.log`       |
| presence-ui        | 8090 | `EmbodiedClaude-PresenceUI` | `run-presence-ui-daemon.ps1`   | `%USERPROFILE%\.config\embodied-claude\logs\presence-ui.log` |


**登録手順**（両方。Web UI を先に — presence-ui は 8080 依存）:

```powershell
cd C:\Users\ma\src\embodied-claude

# 1. 脳（8080）
.\scripts\install-webui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-WebUI

# 2. こよりの部屋（8090）
.\scripts\install-presence-ui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-PresenceUI
```

**再起動後の確認**:

- `http://localhost:8080/projects/...`（Web UI）
- `http://localhost:8090`（こよりの部屋）
- 上記ログに `daemon start` が出ていること

**外すとき**:

```powershell
.\scripts\install-webui-task.ps1 -Uninstall
.\scripts\install-presence-ui-task.ps1 -Uninstall
```

**手動・デバッグ**:


| スクリプト                                                                            | 用途          |
| -------------------------------------------------------------------------------- | ----------- |
| `run-webui-ma-home.ps1` / `restart-webui-ma-home.ps1` / `stop-webui-ma-home.ps1` | Web UI      |
| `run-presence-ui.ps1` / `restart-presence-ui.ps1` / `stop-presence-ui.ps1`       | presence-ui |


**前提（別タスク）**: LM Studio ロード、`.claude/settings.local.json`、`.mcp.json` など。

**memory-mcp は常駐デーモンではない**: Claude Code がチャットごとに `.mcp.json` から子プロセス起動。複数 `claude.exe`（webui セッション + `--continue` など）がいると sociality / memory が複数見える。診断: `.\scripts\check-mcp-processes.ps1`。HTTP recall（:18900）は `memory.db` 直読みにフォールバック。

## Web UI / Surface

- [ ] Surface の 画面構成を考え直そう。
- [ ] マークダウンを表示できるようにしよう。
- [ ] プロンプトをキャンセルする仕組みを追加しよう。
- [x] こより がファイルの書き込みできないみたい。→ `settings.local.json` に Read/Edit/Write + キオスクは `permissionMode: acceptEdits`（`social_chat.py` / `app.js`）。presence-ui 再起動後に :8090 で再テスト。
- [x] 長セッションの二重注入 — `claude_session_resume` で arc サマリのみ（`compose.py` / `social_chat.py`）。

## 記憶・魂のつながり（ぎこちなさ解消）

**現状メモ（2026-06）**: `:8080` で `/memories` → `remember` は保存できている（`memory.db` に入る）。一方キオスク（:8090）や次ターンの会話では「覚えてない／つながってない」ように感じやすい。調査: [mission-A_Investigation-Report.md](./mission-A_Investigation-Report.md)。

- [x] **ミッションA（adapter）** — `HttpMemoryAdapter` 追加。`ORCHESTRATOR_MEMORY_BACKEND=auto`（既定）で HTTP `:18900` → SQLite LIKE フォールバック。presence-ui 再起動で反映。
- [ ] **ミッションA（E2E）** — `remember` 投入後、言い換え発話で `:8090` compose の `[relevant_memories]` に載るか人間確認（memory-mcp 起動中であること）。
- [ ] **保存と想起の一貫性** — `remember` 成功後、次ターンで `list_recent` / `recall` または compose に同じ記憶が載ることを E2E で確認する手順（:8080 と :8090 両方）。
- [x] **キオスク向け記憶 UX（A+B）** — Gateway が「覚えておいて」を検出して `POST :18900/remember` でサーバー側保存。部屋 UI に `room_progress`（文脈を集めてる／考えてる）と `room_activity`（記憶・見る・声など）のコンパクト行を表示。
- [ ] **Gemma の `remember` 信頼性（C）** — サーバー保存後は `[memory_saved_server]` で二重保存を抑止。カテゴリ正規化・口だけ成功の残りは要観察。
- [ ] **初回 remember の遅さ** — e5 埋め込みコールドスタート + `auto_link` でタイムアウトっぽく見える。常駐化・`auto_link` オプション・進捗表示のどれか。
- [ ] **ミッションB/C**（欲求・体験・関係性）— desire / interpretation_shifts / open_loops を compose に載せ切る（魂の強化作戦の続き）。
