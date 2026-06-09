# LM Studio モデル変更手順（ma-home / embodied-claude）

Claude Code・claude-code-webui・wifi-cam ビジョンが LM Studio に送る **model ID** を
揃えるための手順。モデル ID は LM Studio の「Developer → Model Search / Local Server
ログ」で確認した **完全一致の文字列** を使う（例: `google/gemma-4-12b-qat`）。

## 役割分担

| マシン | 役割 |
|--------|------|
| **ma-home** (Windows) | LM Studio 本体、Claude Code CLI、claude-code-webui、koyori キオスクの接続先 |
| **ma-server** (Linux) | 開発・Cursor MCP。Claude Code CLI は動かない（CPU 制約） |
| **koyori** | Chromium キオスク → ma-home の webui のみ |

## クイック手順（ma-home・推奨）

```powershell
cd C:\Users\ma\src\embodied-claude
git pull

# 1) 設定ファイルを一括更新
.\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat

# 2) LM Studio で同じ ID のモデルをロードし、Local Server を起動 (port 1234)

# 3) 設定確認
.\scripts\check-lmstudio-model.ps1

# 4) webui を使う場合は再起動
.\scripts\run-webui-ma-home.ps1
```

テスト送信後、LM Studio の Developer Logs に次のように出れば成功:

```json
"model": "google/gemma-4-12b-qat"
```

`-WhatIf` で変更内容だけ確認できる:

```powershell
.\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat -WhatIf
```

## 更新されるファイル

| ファイル | 内容 |
|----------|------|
| `.claude/settings.local.json` | トップの `"model"` と `env.*MODEL*` をすべて新 ID に |
| `.mcp.json` | `mcpServers.wifi-cam.env.CLAUDE_MODEL` / `LM_STUDIO_VISION_MODEL` |

`settings.local.json` は gitignore 済み（マシンごとのシークレット・設定）。

### モデル関連 env キー（すべて同じ ID に揃える）

- `ANTHROPIC_MODEL`
- `CLAUDE_MODEL` / `LMSTUDIO_MODEL`
- `ANTHROPIC_DEFAULT_SONNET_MODEL` / `OPUS` / `HAIKU`
- `CLAUDE_CODE_SUBAGENT_MODEL`
- `LM_STUDIO_VISION_MODEL`（wifi-cam の画像説明用）

**重要:** トップの `"model": "...-qat"` だけ更新して `env.CLAUDE_MODEL` が古いままだと、
API リクエストだけ非 QAT モデルになることがある。`set-lmstudio-model.ps1` か
`sync-lmstudio-settings.ps1` で揃えること。

## スクリプト一覧

| スクリプト | 用途 |
|------------|------|
| `set-lmstudio-model.ps1` | **モデル ID を変更**（settings + .mcp.json） |
| `set-lmstudio-model.sh` | Linux / ma-server 側の同内容（settings + .mcp.json） |
| `sync-lmstudio-settings.ps1` | `"model"` はそのまま、**env だけ** `"model"` に合わせる（ずれ修正） |
| `check-lmstudio-model.ps1` | 現在の設定・User env・不一致の表示 |
| `run-webui-ma-home.ps1` | webui 起動（WinGet `claude.exe` + MODEL env 強制） |
| `run-claude-local.ps1` | CLI 起動（常に `--model` 付き） |

## 手動で変更する場合

1. LM Studio で新モデルをロードし、Developer → `GET /v1/models` またはログで ID を確認
2. `.claude/settings.local.json` を編集:
   - `"model"` を新 ID に
   - `env` 内の MODEL 系キーをすべて同じ ID に
3. `.mcp.json` の `wifi-cam` → `env` → `CLAUDE_MODEL` / `LM_STUDIO_VISION_MODEL` を更新
4. （任意）Windows ユーザー環境変数に古い `CLAUDE_MODEL` がある場合は削除または更新  
   `set-lmstudio-model.ps1 -UpdateUserEnv` でも可
5. LM Studio Local Server 再起動
6. claude-code-webui 再起動
7. `check-lmstudio-model.ps1` で MISMATCH が無いことを確認

初回のみ:

```powershell
Copy-Item .claude\settings.local.json.example .claude\settings.local.json
notepad .claude\settings.local.json   # ANTHROPIC_AUTH_TOKEN を LM Studio トークンに
```

## ma-server（Linux）での作業

リポジトリの設定だけ先に揃える場合:

```bash
cd ~/src/embodied-claude
./scripts/set-lmstudio-model.sh google/gemma-4-12b-qat
git add -A && git commit ...   # settings.local.json は通常 commit しない
```

Cursor MCP 用の `source scripts/env-lmstudio.sh` は **シェルセッション用**。
永続的なモデル指定は ma-home の `settings.local.json` が本番。

## トラブルシュート

### LM Studio ログが古い model ID のまま

1. `.\scripts\check-lmstudio-model.ps1` → **MISMATCH** 行を確認
2. `.\scripts\sync-lmstudio-settings.ps1` または `set-lmstudio-model.ps1` を再実行
3. webui / CLI を**再起動**（起動時 env を読み直す）
4. LM Studio ログで POST `/v1/messages` の `"model"` を確認

### webui が `spawn EINVAL` になる

Node 24+ では `claude.cmd` を spawn できない。`run-webui-ma-home.ps1` が
WinGet の `claude.exe` を `--claude-path` に渡す。手動起動例:

```powershell
claude-code-webui --host 0.0.0.0 --port 8080 `
  --claude-path "$env:LOCALAPPDATA\Microsoft\WinGet\Links\claude.exe"
```

### wifi-cam が画像を説明できない

- LM Studio 側が **vision 対応**モデルか確認
- `.mcp.json` の `LM_STUDIO_VISION_MODEL` がロード済み ID と一致しているか確認

### memory-mcp の embedding を変えた場合

LM Studio のチャットモデル変更とは別問題。embedding モデルを変えたら memory DB の
再構築が必要（`README.md` の Embedding model 節を参照）。

## 関連

- `.claude/settings.local.json.example` — テンプレート
- `.mcp.json.windows.example` — Windows 用 MCP テンプレート
- `scripts/env-lmstudio.sh` — ma-server シェル用 LM Studio 向け env
- `scripts/setup-ma-home.ps1` — ma-home 初回セットアップ
