# presence-ui — こよりの部屋

Surface / koyori 向け Presence ダッシュボード（FastAPI + Vanilla JS）。

## 起動（ma-home）

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\run-presence-ui.ps1
```

既定は **バックグラウンド起動** — ターミナルはすぐ戻る（8090 は別プロセスで動き続ける）。

| 操作 | コマンド |
|------|----------|
| 起動 | `.\scripts\run-presence-ui.ps1` |
| 停止 | `.\scripts\stop-presence-ui.ps1` |
| 再起動 | `.\scripts\restart-presence-ui.ps1` |
| デバッグ（フォアグラウンド） | `.\scripts\run-presence-ui.ps1 -Foreground` |
| ログオン自動起動 | `.\scripts\install-presence-ui-task.ps1` |

ログ: `%USERPROFILE%\.config\embodied-claude\logs\presence-ui.log`

ブラウザ: http://localhost:8090/

**Native chat**（`PRESENCE_NATIVE_CHAT=1`、install-presence-ui-task 初回作成）では **`:8080` webui 不要**。  
レガシー proxy モードのみ `claude-code-webui` `:8080` が先に必要。

環境変数:

| 変数 | 既定 | 説明 |
|------|------|------|
| `PRESENCE_UI_HOST` | `0.0.0.0` | バインド |
| `PRESENCE_UI_PORT` | `8090` | ポート |
| `PRESENCE_PERSON_ID` | `ma` | social DB の person_id |
| `PRESENCE_SOCIAL_WINDOW_SECONDS` | `900` | social state 窓 |

データソース（MCP を spawn せず直読み）:

- 会話: `~/.claude/sociality/social.db` → `events`
- 状態: desires.json / narrative_arcs / agent_experiences / social-state
- 体温: `system-temperature-mcp`
- カメラ: `wifi-cam-mcp`（`TAPO_*` / `.env`）

## API

- `GET /api/v1/chat`
- `GET /api/v1/koyori/status`
- `GET /api/v1/camera/snapshot`
- `GET /api/v1/health`

## Native chat PoC (claude-code-server)

Python-native Claude CLI wrapper (MIT, `.research/claude-code-server`) embedded via `include_router`.
Requires clone under `.research/` and `uv sync` in `presence-ui/`.

```powershell
$env:PRESENCE_NATIVE_CHAT = "1"
$env:PRESENCE_CCS_PASSWORD = "koyori-poc"   # optional
.\scripts\restart-presence-ui.ps1
```

| Route | 説明 |
|-------|------|
| `POST /api/native/login` | Bearer token（password 上記） |
| `POST /api/native/chat` | SSE; 記憶リストは **Claude を経由せず直接返答**（8192 ctx 対策） |
| `GET /poc/native` | 最小ブラウザテスタ |

記憶リスト以外の native chat は compose **lite**（`PRESENCE_LITE_*`）で append を抑える。LM Studio の ctx が 8192 のときは MCP 定義だけで溢れやすい — リスト質問は direct 経路を使う。

`:8080` プロキシは従来どおり。Native PoC は **並行** で試せる（将来 Node 層を置き換える想定）。
