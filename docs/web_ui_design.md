# こよりWeb UI 設計ドキュメント

## コンセプト
**「魂の可視化」＋ Claude Code 完全ミラー**

Web UI は Claude Code Web UI（`:8080`）の **純粋なクライアント** として動作する。
すべてのセッション操作は Claude Code の API パスをそのまま使い、8090（presence-ui）は **窓（ゲートウェイ）** として振る舞う。

```
Surface / ブラウザ  →  :8090 presence-ui（窓）
                         ├ GET  → 透過プロキシ → :8080 Claude Code（脳）
                         └ POST /api/chat → 社会性フィルター → :8080
```

## 技術スタック
- **窓**: `presence-ui`（FastAPI, Vanilla JS）— `:8090`
- **脳**: `claude-code-webui` — `:8080`
- **社会性**: compose / plan（POST `/api/chat` のみで適用）

---

## API フロー（3 ステップ — 加工禁止）

| ステップ | パス | 役割 |
|---------|------|------|
| 1 | `GET /api/projects` | プロジェクト一覧 |
| 2 | `GET /api/projects/{encodedName}/histories` | セッション一覧（`sessionId` が唯一の ID） |
| 3 | `GET /api/projects/{encodedName}/histories/{sessionId}` | メッセージ履歴 |

送信: `POST /api/chat`（8090 で社会性適用後、8080 へ転送・ストリーム返却）

## 環境変数

| 変数 | 既定 | 説明 |
|------|------|------|
| `CLAUDE_CODE_BACKEND_URL` | `http://127.0.0.1:8080` | Claude Code Web UI |
| `PRESENCE_UI_PORT` | `8090` | こよりの部屋 |

## こより専用（Claude Code セッション API 以外）

- `GET /api/v1/koyori/status` — 欲望・社会状態・体温
- `GET /api/v1/camera/snapshot` — 視界

---

## 📋 タスクリスト

### 【フェーズ1：ゲートウェイ基盤】
- [x] **Claude Code 完全ミラー** — GET 透過プロキシ + POST `/api/chat` 社会性フィルター
- [x] **UI 3 ステップフロー** — projects → histories → history detail
- [ ] **Task 2: 記憶・感情データの連携**（compose 強化）
- [ ] **Task 3: TAPOストリームの統合**

### 【フェーズ2：フロントエンド】
- [x] **Task 4: Web UI スケルトン**
- [x] **Task 5: リアルタイム同期** — 7秒ポーリング（status / chat / camera）
- [ ] **Task 6: 音声フィードバック**

### 【フェーズ1.5：構造的分離（完了）】
- [x] **ストリーム/履歴表示** — `content[type=text]` のみ UI に出す（`thinking` / `tool_use` は非表示）
- [x] **assistant 台詞** — 文字列フィルタせず verbatim 維持（`[excited]` 等の演技タグ含む）
- [ ] **ユーザー履歴** — Phase 2 まで `user_prompt.py` で enriched text を後処理（暫定）

### 【フェーズ2：社会性の構造注入（実装中）】
claude-code-webui をフォークし、社会性を `message` 文字列連結ではなく SDK `appendSystemPrompt` へ移す。

| 項目 | Phase 1.5 | Phase 2 |
|------|-----------|---------|
| 社会性注入 | `message` に prefix 連結 | `appendSystemPrompt`（SDK オプション） |
| まーの発話 | JSONL user text に混ざる | `message` は純粋な発話のみ |
| presence-ui → 8080 | enriched `message` | `message` + `appendSystemPrompt` |
| 表示 | text ブロック抽出 | 同上 + user 履歴の文字列後処理が不要に |

#### API 拡張（`claude-code-webui-ma-home` fork）

`POST /api/chat` ボディ（既存フィールドに加え）:

```json
{
  "message": "まーの純粋な発話",
  "requestId": "uuid",
  "sessionId": "optional",
  "appendSystemPrompt": "[interaction_context]\nphase=chat\n..."
}
```

- **`message`**: ユーザー発話そのもの。Claude Code JSONL の user 行にそのまま記録される。
- **`appendSystemPrompt`**: compose/plan で組み立てた社会性ブロック。モデルへの system 追記のみ。JSONL には残らない。
- presence-ui はこのフィールドを透過転送する（ゲートウェイ側で再加工しない）。

#### データフロー

```
Browser POST /api/chat { message }
    → presence-ui social_chat.py
        compose_interaction_context + plan_response
        → forward { message, appendSystemPrompt }
    → :8080 claude-code-webui-ma-home
        query({ prompt: message, options: { appendSystemPrompt } })
    → Claude CLI → JSONL（user text = message のみ）
```

#### フォーク配置

| パス | 説明 |
|------|------|
| `claude-code-webui-fork/` | upstream `0.1.56` + ma-home 差分 |
| `claude-code-webui-fork/FORK.md` | 差分一覧・ビルド・**push 先リモート**（upstream は archived） |
| `scripts/setup-claude-code-webui-fork.ps1` | build + `npm link` |
| `scripts/run-webui-ma-home.ps1` | `claude-code-webui-ma-home` を優先起動 |

#### チェックリスト

- [x] fork: `ChatRequest.appendSystemPrompt` 型追加
- [x] fork: `chat.ts` → `query({ options: { appendSystemPrompt } })`
- [x] fork: vitest でオプション伝播を検証
- [x] `social_chat.py` — prefix を `appendSystemPrompt` へ（`message` は純粋発話）
- [x] `run-webui-ma-home.ps1` — ma-home fork バイナリ優先
- [ ] `setup-claude-code-webui-fork.ps1` 実行・8080 再起動
- [ ] JSONL 実機確認（user text に社会性ブロックが無いこと）
- [ ] `user_prompt.py` / `stripEnrichedUserPrompt` 削除（履歴クリーンアップ後）

### 【フェーズ3：キオスク】
- [x] **Task 7: キオスク URL** — `koyori-kiosk.sh` / `install-koyori-kiosk.sh` 既定を `http://ma-home.local:8090/projects/...` に変更（8080 直結ではない）
- [ ] **Task 7b: キオスク実機反映** — koyori で `sudo ./install-koyori-kiosk.sh` 再実行（`/etc/default/koyori-kiosk` 更新）
- [ ] **Task 8: イントロ演出**
