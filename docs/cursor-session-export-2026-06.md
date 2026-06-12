# Cursor セッション要約（ma-server → ma-home 移行前）

> **元スレッド:** Cursor Agent on ma-server (`/home/ma/src/embodied-claude`)  
> **transcript ID:** `801b44b9-b414-42cb-8b6a-82fb5cc16df6`  
> **用途:** ma-home で Cursor を開き直すときのコンテキスト引き継ぎ（圧縮版）

---

## 最終アーキテクチャ

| マシン | 役割 |
|--------|------|
| **ma-home** (Win, RTX 3090) | LM Studio (`google/gemma-4-12b-qat`)、Claude Code CLI、claude-code-webui、**全 MCP**、長期記憶 |
| **koyori** (Surface Go, Ubuntu) | Firefox キオスク → ma-home presence-ui `:8090`。BT キーボード（Keychron K4 MAX, Fn+2） |
| **ma-server** (Core2 Linux) | 旧箱（任意）。開発・本番とも ma-home に移行済み |

```
koyori ──webui──▶ ma-home ──LM Studio──▶ Gemma
                      └── MCP / memory / wifi-cam / sociality / tts …
```

---

## このスレッドで完了したこと

### ma-home セットアップ

- repo clone、`setup-ma-home.ps1`、`.mcp.json`（Windows パス）
- LM Studio 連携: `ANTHROPIC_BASE_URL=http://127.0.0.1:1234`、`settings.local.json`
- MCP 接続: memory / sociality / system-temperature / tts / **wifi-cam**
- エージェント名 **「こより」** に統一（desire-system、SOUL テンプレ等）
- desire / auto_context / hooks / talk スキル方向の自動化を追加

### wifi-cam（Tapo `192.168.10.116`）

- パスワードに `"` 含む → PowerShell は **単一引用符** `'1qaz"WSX…'`
- ONVIF snapshot 失敗時 **RTSP フォールバック** で 1920×1080 取得 OK
- LM Studio 経由の tool_result 400 → **text-only tool result** + **LM Studio 側で vision describe**（`/see` スキル）
- 幻覚キャプション問題 → vision describe パイプラインで実画面と一致する説明まで到達

### koyori キオスク

- Ubuntu Server 24.04 + 有線固定 IP + `koyori.local`
- **Firefox キオスク**（Chromium から変更）、xrandr 1800×1200 フルスクリーン
- Mozc IME（半/全）、Firefox プロファイルは `~/snap/firefox/.../koyori-kiosk`（snap 制約回避）
- **Keychron K4 MAX** BT ペア（Fn+2）、ReconnectUUIDs + watch スクリプト
- Input Leap / onboard タッチ KB → **見送り**（`docs/backlog-koyori.md`）

### webui / thinking 表示

- claude-code-webui on ma-home（`scripts/run-webui-ma-home.ps1`）
- `System (thinking_tokens)` JSON 洪水 → LM Studio Thinking off + **`CLAUDE_CODE_DISABLE_THINKING=1`**

---

## 重要パス・設定（本番 = ma-home）

| 項目 | 場所 |
|------|------|
| repo | `C:\Users\ma\src\embodied-claude` |
| MCP | `.mcp.json`（Windows パス） |
| Claude env | `.claude/settings.local.json` |
| 人格 | `SOUL.md` / `MEMORY.md`（gitignore 可） |
| LM Studio token | `%USERPROFILE%\.config\embodied-claude\lmstudio.token` |
| 長期記憶 DB | `%USERPROFILE%\.claude\memories\` |
| webui（脳・デバッグ） | `http://ma-home:8080/projects/C:/Users/ma/src/embodied-claude` |
| こよりの部屋（presence-ui） | `http://ma-home.local:8090/` |
| koyori キオスク URL（既定） | `http://ma-home.local:8090/`（`/etc/default/koyori-kiosk` の `KOYORI_WEBUI_URL`） |

**ma-server から移す必要は基本なし**（上記は ma-home で既に運用中）。

---

## 未完了・バックログ

- ma-home **webui 常時起動** → `scripts/install-webui-task.ps1`（`docs/backlog-ma-home.md`）
- koyori **内蔵カメラ**（libcamera / video グループ / 場合により linux-surface）— 近目 PoC 用、本番目は Tapo
- koyori タッチキーボード、Input Leap — 見送り
- ~~開発ワークスペースを ma-home Cursor に移す~~ → **完了**（2026-06）

---

## ma-home Cursor 移行（最小手順）

> **2026-06 完了済み。** 以下は移行当時の記録。新規作業は ma-home ローカルで `git pull` のみ。

1. ma-server で **未 push が無い**ことを確認 → push
2. ma-home: `git pull`（秘密ファイルは `sync-ma-home-git.ps1`）
3. Cursor: **Remote SSH 切断** → `C:\Users\ma\src\embodied-claude` をローカルで Open Folder
4. 以降: ma-home で編集・push / koyori はキオスク更新時だけ pull

### 消えるもの / 残るもの

| 消える | 残る |
|--------|------|
| ma-server 紐づけ Cursor Agent チャット | git、SOUL/MEMORY、memory-mcp |
| （許容なら）このスレッドの UI 履歴 | webui History（ma-home）、本番設定 |

---

## モデル・env メモ

- モデル ID: **`google/gemma-4-12b-qat`**（QAT 版を settings + env 全体で統一）
- 変更: `.\scripts\set-lmstudio-model.ps1` / `check-lmstudio-model.ps1`
- thinking 無効: `"CLAUDE_CODE_DISABLE_THINKING": "1"` in `settings.local.json` env

---

## 関連ドキュメント

- `docs/VISION.md` — プロジェクトの前提・目指すもの
- `docs/lmstudio-model-change.md`
- `docs/koyori-kiosk-ime.md`
- `docs/koyori-input-sharing.md`（Keychron）
- `docs/backlog-koyori.md` / `docs/backlog-ma-home.md`

---

*圧縮要約。詳細は git 履歴と上記 docs を参照。*
