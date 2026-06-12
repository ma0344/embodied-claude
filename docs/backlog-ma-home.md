# ma-home / koyori バックログ

あとでやること。完了したら行を消すか `[x]` にする。

## システム起動時: Claude Code Web UI + presence-ui を Daemon 常時起動

**やりたいこと**: Windows ログオン（システム起動後）に、脳（:8080）とこよりの部屋（:8090）を自動で立ち上げ、落ちたら再起動する。

**状態**: スクリプトは揃っている。**Scheduled Task の登録・再起動後の動作確認は未着手**。

| サービス | ポート | Scheduled Task | Daemon | ログ |
|----------|--------|----------------|--------|------|
| Claude Code Web UI | 8080 | `EmbodiedClaude-WebUI` | `run-webui-ma-home-daemon.ps1` | `%USERPROFILE%\.config\embodied-claude\logs\webui.log` |
| presence-ui | 8090 | `EmbodiedClaude-PresenceUI` | `run-presence-ui-daemon.ps1` | `%USERPROFILE%\.config\embodied-claude\logs\presence-ui.log` |

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

| スクリプト | 用途 |
|------------|------|
| `run-webui-ma-home.ps1` / `restart-webui-ma-home.ps1` / `stop-webui-ma-home.ps1` | Web UI |
| `run-presence-ui.ps1` / `restart-presence-ui.ps1` / `stop-presence-ui.ps1` | presence-ui |

**前提（別タスク）**: LM Studio ロード、`.claude/settings.local.json`、`.mcp.json`、memory-mcp 常駐など。
