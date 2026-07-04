# LM Studio モデル変更手順（ma-home / embodied-claude）

Claude Code・claude-code-webui・wifi-cam ビジョンが LM Studio に送る **model ID** を
揃えるための手順。モデル ID は LM Studio の「Developer → Model Search / Local Server
ログ」で確認した **完全一致の文字列** を使う（例: `google/gemma-4-12b-qat`）。

## 役割分担

| マシン | 役割 |
|--------|------|
| **ma-home** (Windows) | LM Studio 本体、Claude Code CLI、claude-code-webui、全 MCP、開発（Cursor ローカル） |
| **koyori** (Surface Go) | Firefox キオスク → ma-home の presence-ui `:8090`（表示・入力端末） |
| **ma-server** (Linux) | 旧開発箱（任意）。本番経路・開発の主戦場ではない |

## クイック手順（ma-home・推奨）

```powershell
cd C:\Users\ma\src\embodied-claude
git pull

# 1) チャットモデル（Gemma 等）
.\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat

# 1b) vision スロット（Qwen2.5-VL-3B Q4_K_M ロード後、GET /v1/models の id を指定）
.\scripts\set-lmstudio-model.ps1 -VisionModel qwen/qwen2.5-vl-3b-instruct

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
- `LM_STUDIO_VISION_MODEL`（wifi-cam / gateway の **画像説明専用**。チャットモデルと別 ID）

**重要:** トップの `"model": "...-qat"` だけ更新して `env.CLAUDE_MODEL` が古いままだと、
API リクエストだけ非 QAT モデルになることがある。`set-lmstudio-model.ps1` か
`sync-lmstudio-settings.ps1` で揃えること。

**二モデル構成（2026-06〜）:** チャット = `google/gemma-4-12b-qat`、vision = **`google/gemma-4-e4b`**（classifier と同ロード可）。KV キャッシュを分離する。

**vision 切替（2026-06-29）:** Qwen2.5-VL-3B から e4b へ。手順: `.\scripts\enable-vis-e4b-ma-home.ps1` → LM Studio で Qwen unload → `restart-presence-ui.ps1`。

## SOUL.core — 表層チャットの人格（Surface Direct 本線）

**Surface Direct（`PRESENCE_SURFACE_DIRECT=1`）**: SOUL は **gateway が毎ターン `build_gateway_stable_append()` で注入**。
`presets/koyori-SOUL.core.md` を編集 → `presence-ui` 再起動で反映。**LM Studio のチャットモデル System Prompt は空**にする（二重・矛盾を防ぐ）。

| 項目 | 値 |
|------|------|
| ファイル | `presets/koyori-SOUL.core.md`（リポジトリ内・コミット可） |
| 注入 | `PRESENCE_SOUL_CORE_IN_APPEND=1`（既定・ma-home 推奨） |
| LM Studio チャット | **System Prompt 空** — vision モデルには貼らない |

```powershell
# SOUL 更新後
.\scripts\restart-presence-ui.ps1
# LM Studio: google/gemma-4-12b-qat の System Prompt を空にして Local Server 再起動
```

**Legacy（RP Phase 1 / LM Studio 側 SOUL）:** `PRESENCE_SOUL_CORE_IN_APPEND=0` + LM Studio に core 全文コピペ。
Surface Direct では非推奨。

詳細 → [surface-direct-llm.md](../tracks/surface-direct-llm.md) · [role-persistence-ma-home.md](./role-persistence-ma-home.md)

## Vision スロット（こよりの目）

チャット（Gemma）と **別モデルを LM Studio に同時ロード**し、`:1234` の `"model"` フィールドで振り分ける。

### 推奨（ma-home・第一候補）

| 項目 | 値 |
|------|-----|
| モデル | **Qwen2.5-VL-3B-Instruct** — `lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF` の **Q4_K_M** + **mmproj**（2 ファイル構成） |
| 用途 | Tapo キャプション・自律 `observe_room`・会話の「見て」prefetch |
| Context length | **8192**（vision だけ。262k は不要で VRAM を食う） |
| Max Concurrent Predictions | **1** |
| GPU offload | 最大（vision モデル側） |

**LM Studio Discover（推奨）:** `qwen2.5-vl-3b` → `lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF` を選び **Q4_K_M** をダウンロードすると、本体 `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` と `mmproj-model-f16.gguf` が**同じフォルダにまとめて**入る（手動で mmproj を探す必要は通常ない）。Load 後、モデル名横に**黄色い目アイコン**が出れば vision 有効。

**HF から手動する場合:** [同リポ](https://huggingface.co/lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF) から上記 2 ファイルを取得し、`%USERPROFILE%\.lmstudio\models\lmstudio-community\Qwen2.5-VL-3B-Instruct-GGUF\` など**同一ディレクトリ**に置く。mmproj だけ別フォルダだとテキスト専用になる。

ロード後 **Developer ログ** または `GET http://127.0.0.1:1234/v1/models` の `id` をコピー（例: `qwen/qwen2.5-vl-3b-instruct` — **実機の文字列が正**）。

### `presence-ui.local.env`（または wifi-cam / `.mcp.json` の env）

`%USERPROFILE%\.config\embodied-claude\presence-ui.local.env` に追記（コミットしない）:

```env
# チャットは settings.local.json の Gemma のまま
LM_STUDIO_VISION_MODEL=<上でコピーした ID>

# 解像度・説明文（こよりの目 — 情報量と速度のバランス）
WIFI_CAM_VISION_MAX_SIDE=1024
WIFI_CAM_VISION_MAX_TOKENS=720
WIFI_CAM_VISION_PROMPT=この部屋の写真。見えているものを具体的に日本語で書いてください。人物・姿勢・家具・明るさ・窓やモニタの有無。推測や見えないことは書かない。5〜8文程度。
# WIFI_CAM_VISION_USE_SYSTEM=1   # 既定: 上を system に、user は「この写真を説明してください。」
# WIFI_CAM_VISION_USER_TEXT=この写真を説明してください。
```

```powershell
.\scripts\restart-presence-ui.ps1
```

### 動作確認

1. LM Studio ログで vision リクエストの `"model"` が Qwen2.5-VL になっていること
2. `:8090` または自律 tick 後、キャプションが日本語で返ること
3. チャット2ターン目の `f_keep` が、vision 前より改善していること（別ロードなので干渉しない）

### 量子化を上げる場合

部屋の細部が足りなければ **Q6_K / Q8_0**（3B リポに Q5 は無い）に差し替え。mmproj はそのまま。3090 + Gemma 12B QAT でも **vision ctx 8k** なら多くの場合載る。

### 関連 env（コード側）

| 変数 | 既定 | 説明 |
|------|------|------|
| `LM_STUDIO_VISION_MODEL` | `CLAUDE_MODEL` | vision API の model ID |
| `WIFI_CAM_VISION_MAX_SIDE` | 1024 | JPEG 長辺リサイズ |
| `WIFI_CAM_VISION_MAX_TOKENS` | 720 | キャプション最大トークン |
| `WIFI_CAM_VISION_PROMPT` | 日本語・実見のみ | 指示全文（既定は **system** に載せる） |
| `WIFI_CAM_VISION_USE_SYSTEM` | `1` | `0` で従来どおり user メッセージに統合 |
| `WIFI_CAM_VISION_USER_TEXT` | この写真を説明してください。 | user turn の短文 |
| `WIFI_CAM_VISION_API` | auto | `chat` / `messages` 固定も可 |

詳細: [lmstudio-kv-cache.md](./lmstudio-kv-cache.md)（チャット KV と vision 分離の背景）。

## スクリプト一覧

| スクリプト | 用途 |
|------------|------|
| `set-lmstudio-model.ps1` | **チャット** model ID を変更（`-VisionModel` で vision 別指定） |
| `set-lmstudio-model.sh` | Linux 用（レガシー。ma-home では `set-lmstudio-model.ps1` を使う） |
| `sync-lmstudio-settings.ps1` | `"model"` はそのまま、**env だけ** `"model"` に合わせる（ずれ修正） |
| `check-lmstudio-model.ps1` | 現在の設定・User env・不一致の表示 |
| `run-webui-ma-home.ps1` | webui 起動（WinGet `claude.exe` + MODEL env 強制） |
| `run-claude-local.ps1` | CLI 起動（常に `--model` 付き） |

## 手動で変更する場合

1. LM Studio で新モデルをロードし、Developer → `GET /v1/models` またはログで ID を確認
2. `.claude/settings.local.json` を編集:
   - `"model"` を新 ID に
   - `env` 内の MODEL 系キーをすべて同じ ID に
3. `.mcp.json` の `wifi-cam` → `env` → `CLAUDE_MODEL`（チャット用）を更新。  
   **`LM_STUDIO_VISION_MODEL` は vision 専用モデル**（チャットと同じ ID にしない）→ [Vision スロット](#vision-スロットこよりの目) を参照
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

## Linux / ma-server（レガシー・任意）

開発は ma-home に移行済み。Linux マシンで設定ファイルだけ揃える場合:

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

- LM Studio で **Qwen2.5-VL-3B + mmproj** がロード済みか確認（Gemma 単体では vision 専用スロットにならない）
- `LM_STUDIO_VISION_MODEL` がロード済み ID と一致しているか（`presence-ui.local.env` / `.mcp.json`）
- `GET /v1/models` で vision 用 `id` を再確認

### memory-mcp の embedding を変えた場合

LM Studio のチャットモデル変更とは別問題。embedding モデルを変えたら memory DB の
再構築が必要（`README.md` の Embedding model 節を参照）。

## 関連

- `.claude/settings.local.json.example` — テンプレート
- `.mcp.json.windows.example` — Windows 用 MCP テンプレート
- `scripts/env-lmstudio.sh` — Linux シェル用 LM Studio 向け env（レガシー）
- `scripts/setup-ma-home.ps1` — ma-home 初回セットアップ
