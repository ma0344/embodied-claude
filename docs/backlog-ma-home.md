# ma-home / koyori バックログ

あとでやること。完了したら行を消すか `[x]` にする。

## ma-home: claude-code-webui 常時起動

**スクリプトは既にある**（未セットアップなら後で実行）:

| ファイル | 用途 |
|----------|------|
| `scripts/run-webui-ma-home-daemon.ps1` | 落ちたら再起動 + `~/.config/embodied-claude/logs/webui.log` |
| `scripts/install-webui-task.ps1` | Windows ログオン時 Scheduled Task に登録 |

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\install-webui-task.ps1
Start-ScheduledTask -TaskName EmbodiedClaude-WebUI
```

外すとき: `.\scripts\install-webui-task.ps1 -Uninstall`

関連: `scripts/run-webui-ma-home.ps1` / `.cmd`（手動起動）
