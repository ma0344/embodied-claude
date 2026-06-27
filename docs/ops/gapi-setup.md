# GAPI — OAuth セットアップ（ma-home）

**対象**: GAPI-1 · OAuth（まー個人）  
**トラック**: [tracks/gapi.md](../tracks/gapi.md)  
**ポリシー例**: [examples/configs/gapi-policy.example.toml](../../examples/configs/gapi-policy.example.toml)

---

## 1. Google Cloud プロジェクト

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成（例: `embodied-claude-ma-home`）
2. **API とサービス → ライブラリ** で有効化:
   - **Google Calendar API**
   - **Google Drive API**（Phase 1b 以降）
   - **Google Docs API**（Phase 2 書込以降）
3. **OAuth 同意画面** — 外部 / テストユーザーにまーの Google アカウントを追加

---

## 2. OAuth クライアント（API キーではない）

**まーの Calendar / Drive にアクセスするには OAuth 2.0 デスクトップクライアント JSON が必要。**  
API キーだけでは **個人カレンダーの読取・書込はできない**（公開データ向け）。

| 持ち物 | 使う？ |
|--------|--------|
| **OAuth 2.0 クライアント ID JSON**（Desktop） | ✅ **これ** |
| API キー | ❌ GAPI では不使用 |

1. Cloud Console → **認証情報 → OAuth 2.0 クライアント ID** → **デスクトップアプリ**
2. JSON をダウンロード → 例: `scripts/google-oauth-client.json`（gitignore 済）
3. または `GOOGLE_OAUTH_CREDENTIALS_PATH` でパス指定

Web アプリ型 JSON（`"web": { ... }`）は **不可** — Desktop 型（`"installed"`）に作り直す。

---

## 3. GAPI-prep-1 — 初回 consent + list smoke

```powershell
# OAuth JSON を配置（例）
# copy Download\client_secret_....json scripts\google-oauth-client.json

cd C:\Users\ma\src\embodied-claude\presence-ui
uv sync
uv run google-oauth-consent
uv run gapi-calendar-smoke
uv run gapi-calendar-smoke --prefetch
```

リポジトリ直下から:

```powershell
uv run python scripts\google_oauth_consent.py
uv run python scripts\gapi_calendar_list_smoke.py --prefetch
```

**環境変数（任意）**

```env
GOOGLE_OAUTH_CREDENTIALS_PATH=C:/Users/ma/.claude/google/google-oauth-client.json
GOOGLE_OAUTH_TOKEN_PATH=C:/Users/ma/.claude/google/oauth-token.json
GAPI_POLICY_PATH=C:/Users/ma/src/embodied-claude/gapi-policy.toml
```

`gapi-policy.toml` はリポジトリ直下 walk-up で自動検出（gitignore 済み）。

---

## 4. OAuth クライアント（参照）

**アプリケーションの種類**: デスクトップアプリ（ma-home Windows）

---

## 5. スコープ（段階）

| Phase | スコープ | 用途 |
|-------|----------|------|
| **1 — Calendar 読取** | `https://www.googleapis.com/auth/calendar.readonly` | GAPI-2 |
| **1.5 — Calendar 書込** | `https://www.googleapis.com/auth/calendar.events` | GAPI-7（create / update） |
| **2a — Drive 読取** | `https://www.googleapis.com/auth/drive.readonly` 等 | GAPI-4 |
| **2b — Drive 書込** | `https://www.googleapis.com/auth/drive.file` | GAPI-6 |

**推奨 consent 順**:

1. 開発初期: `calendar.readonly` のみ → GAPI-2 E2E
2. Calendar 書込: **`calendar.events` に差し替え or 追加 consent** → GAPI-7  
   （`calendar.events` は読取も含むので、1.5 以降はこれ1本でも可）
3. Drive 読取 / 書込: 別途 consent

`calendar`（フル）スコープは **使わない** — カレンダー削除・ACL 変更まで許すため過剰。

---

## 6. 環境変数（presence-ui / ma-home）

```env
# Git にコミットしない — ~/.claude/ または presence-ui/.env

GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=....

# refresh token 取得後（GAPI-1 実装が書き込むパス）
GOOGLE_OAUTH_TOKEN_PATH=C:/Users/ma/.claude/google/oauth-token.json

# ポリシー（任意 — 未設定時は socialPolicy walk-up）
# GAPI_POLICY_PATH=C:/Users/ma/src/embodied-claude/examples/configs/gapi-policy.example.toml

PRESENCE_GAPI_ENABLED=0
PRESENCE_GAPI_CALENDAR_PREFETCH=1
# Phase 1.5 以降
PRESENCE_GAPI_CALENDAR_WRITE=0
```

`PRESENCE_GAPI_ENABLED=1` は GAPI-2 配線後。

---

## 7. 初回 consent（実装済 — GAPI-prep-1）

`uv run google-oauth-consent` — 上記 §3 参照。

---

## 8. 共有カレンダー

1. Google Calendar UI で対象カレンダーの **設定 → カレンダーの統合** から **カレンダー ID** をコピー
2. `gapi-policy.example.toml` の `[[google.calendars]]` に追加、`enabled = true`

primary は `id = "primary"` のまま。

---

## 9. Drive フォルダ（Phase 2a）

1. Drive でこより用フォルダを作成（または既存共有フォルダ）
2. フォルダ URL から `folder_id` を取得
3. `[[google.drive_roots]]` に記載

書込 Phase 2 では **同フォルダ** に `allow_create = true`。

---

## 10. 運用

| 事象 | 対応 |
|------|------|
| token 期限切れ / revoke | 再 consent。status は `expired` |
| API quota | prefetch 窓 today+tomorrow のみ（既合意） |
| 切断時 | 表層は「繋がってへん」— 捏造禁止 |

---

## 11. チェックリスト

- [ ] Cloud プロジェクト + Calendar API 有効
- [ ] OAuth デスクトップクライアント作成
- [ ] primary + 共有カレンダー ID 一覧
- [ ] Drive フォルダ ID（1b 用）
- [ ] `gapi-policy.example.toml` を ma-home 用にコピー・編集
- [ ] GAPI-2 E2E: 「今日の予定は？」
- [ ] GAPI-7 E2E: 「来週火曜15時に〇〇、カレンダー入れといて」
- [ ] 共有カレンダーで `allow_create` が効くこと（書込先をポリシーで限定）
