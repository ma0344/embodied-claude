# GAPI — OAuth セットアップ（ma-home）

**対象**: GAPI-1 · OAuth（まー個人）  
**トラック**: [tracks/gapi.md](../tracks/gapi.md)（**prep-1/2/3 ✅**）  
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

## 3b. GAPI-prep-2 — Calendar 書込 smoke

**前提**

1. `calendar.events` スコープで再 consent:
   ```powershell
   cd C:\Users\ma\src\embodied-claude\presence-ui
   uv run google-oauth-consent --scope events
   ```
2. `gapi-policy.toml` の primary（または対象カレンダー）で:
   ```toml
   allow_create = true
   allow_update = true
   allow_delete = false   # v1 では delete API 非公開のまま
   ```

**create + patch smoke**（`[gapi-smoke]` プレフィックス付きテスト予定）:

```powershell
uv run gapi-calendar-write-smoke --dry-run
uv run gapi-calendar-write-smoke
```

リポジトリ直下から:

```powershell
uv run python scripts\gapi_calendar_write_smoke.py --dry-run
uv run python scripts\gapi_calendar_write_smoke.py
```

成功時: 明日 10:00–10:30 に作成 → +1h へ patch。event id / link を表示。  
削除 API は v1 未実装 — `[gapi-smoke]` イベントは Calendar UI から手動削除可。

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

PRESENCE_GAPI_ENABLED=1
PRESENCE_GAPI_CALENDAR_PREFETCH=1
# GAPI-2r-S2 — chat read: cue → Stage1 calendar_read → pipeline（0 で L0 cue のみに戻す）
PRESENCE_GAPI_CALENDAR_READ_STAGED=1
# GAPI-7 — 明示の「入れておいて」「ずらして」で events.insert/patch
PRESENCE_GAPI_CALENDAR_WRITE=1
# GAPI-7b — Stage2 抽出 + 確認後に書込（既定 ON）
PRESENCE_GAPI_CALENDAR_CONFIRM=1
PRESENCE_GAPI_CALENDAR_STAGED=1
# GAPI-2b/2s — 発話窓・キーワード（0 で e4b 窓/検索 OFF · C4 のみ）
PRESENCE_GAPI_READ_WINDOW_E4B=1
PRESENCE_GAPI_READ_SEARCH_E4B=1
# gateway e4b 診断ログ（既定 ON → ~/.claude/logs/gateway-llm.log）
PRESENCE_GATEWAY_LLM_LOG=1
```

`PRESENCE_GAPI_ENABLED=1` で router が L0 calendar intent 時に `[calendar_prefetch]` を注入する（`おはよ` だけでは API を叩かない）。

**7b（既定）** `PRESENCE_GAPI_CALENDAR_CONFIRM=1`  
e4b Stage2 で日時・タイトル抽出 → 不足なら質問 → 揃ったら「この内容で入れていい？」→ まーが `OK` → gateway 書込 → 「入れたで」。

**7a 即時** `PRESENCE_GAPI_CALENDAR_CONFIRM=0` — regex 直書き（確認なし）。

---

## 7. 下準備フェーズ（進捗）

| Prep | CLI | ma-home | router |
|------|-----|---------|--------|
| **prep-1** | `gapi-calendar-smoke` / `--prefetch` | ✅ | — |
| **prep-2** | `gapi-calendar-write-smoke` | ✅ | — |
| **prep-3** | — | — | ✅ `calendar_prefetch` · native_chat_router |
| **GAPI-7** | — | — | ✅ `calendar_write` · create + patch（`PRESENCE_GAPI_CALENDAR_WRITE=1`） |
| **GAPI-7b** | — | — | ✅ Stage2 + 確認（返事正規化 · 表層ガード） |
| **GAPI-7c** | — | — | 📋 1発話・複数 create（[gapi.md §7c](../tracks/gapi.md#gapi-7c--複数予定の一括書込)） |
| **GAPI-7d** | — | — | 📋 確認返事 e4b 分類（[gapi.md §7d](../tracks/gapi.md#gapi-7d--確認返事の-e4b-分類)） |
| **GAPI-2b** | `gapi-calendar-read-window-smoke` | ✅ 窓解決 + list | ✅ router prefetch 実 API |
| **GAPI-2s** | — | ✅ 来月+キーワード（東口・入浴介助） | ✅ kiosk E2E |

### GAPI-2b ma-home 検証

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\restart-presence-ui.ps1   # コード反映後
cd presence-ui
uv run gapi-calendar-read-window-smoke
uv run gapi-calendar-read-window-smoke --utterance "来週の予定は？" --show-block
```

`PRESENCE_GAPI_ENABLED=1` · `presence-ui.local.env` 読込済みであること。表層まで含む E2E は kiosk から「来週の予定は？」。

---

## 8. 初回 consent（prep-1）

`uv run google-oauth-consent` — 上記 §3 参照。

---

## 9. 共有カレンダー

1. Google Calendar UI で対象カレンダーの **設定 → カレンダーの統合** から **カレンダー ID** をコピー
2. `gapi-policy.example.toml` の `[[google.calendars]]` に追加、`enabled = true`

primary は `id = "primary"` のまま。

---

## 10. Drive フォルダ（Phase 2a）

1. Drive でこより用フォルダを作成（または既存共有フォルダ）
2. フォルダ URL から `folder_id` を取得
3. `[[google.drive_roots]]` に記載

書込 Phase 2 では **同フォルダ** に `allow_create = true`。

---

## 11. 運用

| 事象 | 対応 |
|------|------|
| token 期限切れ / revoke | 再 consent。status は `expired` |
| API quota | prefetch 窓 today+tomorrow のみ（既合意） |
| 切断時 | 表層は「繋がってへん」— 捏造禁止 |

---

## 12. チェックリスト

**インフラ（ma-home）**

- [x] Cloud プロジェクト + Calendar API 有効
- [x] OAuth デスクトップクライアント作成
- [x] Test user 追加（Testing モード時）
- [x] `gapi-policy.toml` を ma-home 用にコピー・編集
- [x] prep-1: list smoke / `--prefetch`
- [x] prep-2: write smoke（create + patch · `[gapi-smoke]`）

**未（意図的に後回し）**

- [ ] primary + 共有カレンダー ID 一覧（共有は必要時）
- [ ] Drive フォルダ ID（Phase 2a）
- [x] **prep-3**: router 実線（`calendar_prefetch` · L0 intent）
- [x] **GAPI-2b** CLI/router smoke（`gapi-calendar-read-window-smoke` · 実 Calendar API）
- [x] **GAPI-2 表層 E2E**（2026-07-01 kiosk）: 来月 / 来週 / 明日から一週間 — prefetch 根拠で応答
- [x] **GAPI-2s E2E**（2026-07-01）: `来月の東口の予定は？` · `来月の入浴介助の予定を全部教えて` — C4 窓 + `q=` 絞り込み
- [ ] GAPI-7 E2E: 会話「来週火曜15時に〇〇、カレンダー入れといて」
- [ ] 共有カレンダーで `allow_create` が効くこと（書込先をポリシーで限定）
