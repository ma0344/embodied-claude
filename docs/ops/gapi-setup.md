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

## 2. OAuth クライアント

**アプリケーションの種類**: デスクトップアプリ（ma-home Windows）

1. **認証情報 → OAuth 2.0 クライアント ID** を作成
2. クライアント ID / シークレットを **git 外** に保存

---

## 3. スコープ（段階）

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

## 4. 環境変数（presence-ui / ma-home）

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

## 5. 初回 consent（手順イメージ）

実装前の合意:

1. `uv run python scripts/google_oauth_consent.py`（**未実装** — GAPI-1 で追加予定）
2. ブラウザでまーがログイン → refresh token を `GOOGLE_OAUTH_TOKEN_PATH` に保存
3. `check-koyori-stack.ps1` または `koyori/status` で `google_calendar: connected`

---

## 6. 共有カレンダー

1. Google Calendar UI で対象カレンダーの **設定 → カレンダーの統合** から **カレンダー ID** をコピー
2. `gapi-policy.example.toml` の `[[google.calendars]]` に追加、`enabled = true`

primary は `id = "primary"` のまま。

---

## 7. Drive フォルダ（Phase 1b）

1. Drive でこより用フォルダを作成（または既存共有フォルダ）
2. フォルダ URL から `folder_id` を取得
3. `[[google.drive_roots]]` に記載

書込 Phase 2 では **同フォルダ** に `allow_create = true`。

---

## 8. 運用

| 事象 | 対応 |
|------|------|
| token 期限切れ / revoke | 再 consent。status は `expired` |
| API quota | prefetch 窓 today+tomorrow のみ（既合意） |
| 切断時 | 表層は「繋がってへん」— 捏造禁止 |

---

## 9. チェックリスト（実装前）

- [ ] Cloud プロジェクト + Calendar API 有効
- [ ] OAuth デスクトップクライアント作成
- [ ] primary + 共有カレンダー ID 一覧
- [ ] Drive フォルダ ID（1b 用）
- [ ] `gapi-policy.example.toml` を ma-home 用にコピー・編集
- [ ] GAPI-2 E2E: 「今日の予定は？」
- [ ] GAPI-7 E2E: 「来週火曜15時に〇〇、カレンダー入れといて」
- [ ] 共有カレンダーで `allow_create` が効くこと（書込先をポリシーで限定）
