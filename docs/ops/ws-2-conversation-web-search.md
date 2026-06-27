# WS-2 — 会話中 Web 検索・URL 閲覧（仕様）

**合意**: 2026-06-23（まー — 松本市請求様式の会話を契機）  
**関連**: [backlog-ma-home.md](../backlog-ma-home.md)（MEM-5j / WS-1〜4）、[ws-5-spontaneous-search.md](./ws-5-spontaneous-search.md)（自発検索・北極星シナリオ）、[gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[intent-bucket-flow.md](../architecture/intent-bucket-flow.md)

---

## 1. 問題（実例）

まー: 「松本市の…請求様式ってオンラインのどこかにあるか調べてもらえる？」

こよりの応答は:

- 「探してみる」→ **一般論**（社会福祉協議会、障害福祉ページを当てに行く）
- `Sources:` が **曖昧**（具体 URL なし）
- まーが検索語を指定しても **ヒットしない**
- まーが `https://www.city.matsumoto.nagano.jp/soshiki/61/194124.html` を貼ったあと、「補助金／委託で分かれてる」など **ページ固有の説明**

**疑問（まー）**: 最後の説明はページを見ないとわからない — 本当に見てる？

### 1.1 現状の答え（2026-06-23 時点）

| 経路 | 会話中 | 実 URL 取得 | ページ本文取得 |
|------|--------|-------------|----------------|
| CC `WebSearch` | ✅ 使われている | ❌ 多く `searchCount: 0` | ❌ |
| CC `WebFetch` | 権限はあるが LM Studio 本線では **未確認・未ルーティング** | — | ツールが呼ばれなければ ❌ |
| `web_search_direct`（DDG Instant） | **自律 tick のみ** | △ Instant Answer のみ | ❌ |
| gateway `vision_prefetch` 型の **URL prefetch** | **なし** | — | **なし** |

**結論**: まーが URL を貼る前のターンは **検索できていない（または空結果を捏造）**。URL 貼付後の「補助金／委託」説明は、**ページ取得が JSONL に残っていなければ、訓練データ由来の当て推量の可能性が高い**。仕様上は **「見た」と言ってはいけない**。

---

## 2. 目標

1. 会話の「調べて」「検索して」は **gateway が先に検索**し、結果を `gateway_turn_context` に載せる（LLM にツール名を選ばせない）。
2. メッセージ内の **http(s) URL** は gateway が **取得・要約**してから応答（`see_prefetch` / `vision_prefetch` と同型）。
3. 検索結果・取得失敗は **正直に報告**（Sources 捏造禁止）。
4. 松本市請求様式のような **行政・様式 PDF** でも、**URL 候補 2〜3 件**まで届くバックエンド（WS-2b）。

---

## 3. 非目標（v1）

- ページ内 PDF のダウンロード・フォーム記入代行
- 全 Web の自由クロール
- Google カレンダー / ドライブ（別トラック **GAPI**）

---

## 4. アーキテクチャ

```
まー発話
  → resolve_user_intent / hybrid_intent（+ search_intent, url_intent）
  → intercept_chat_request_async
       ├─ search_prefetch（WS-2a/2b）→ [web_search_prefetch]
       ├─ url_prefetch（WS-2c）      → [url_prefetch]
       └─ compose / plan（既存）
  → enriched user message → LM Studio
  → 応答（prefetch を根拠に述べる；根拠なし Sources 禁止）
```

**原則**: CC `WebSearch` / `WebFetch` は native chat から **外す**（WS-3）。身体は gateway 直実行。

---

## 5. フェーズ

### WS-1 — 空検索の正直化（小）

| 項目 | 内容 |
|------|------|
| UI | `chat-markdown.js` — tool_result が空なら Sources をリンク化しない + 「検索できなかった」注記 |
| plan | `must_avoid`: 根拠のない URL・Sources |
| 権限 | WS-3 と同時でも可 |

**受け入れ**: 空 WebSearch 後に捏造 Google URL が出ない。

### WS-2a — 会話検索の gateway ルーティング（中）

| 項目 | 内容 |
|------|------|
| intent | `user_intent` に `wants_web_search` — 「調べて」「検索」「ネットで」「どこにある」+ 名詞句 |
| query 抽出 | まー発話から検索語を抽出（ルール優先；長文は先頭 120 字 or LLM 1 行は後追い可） |
| 実行 | `web_search_for_message(query)` — 初期は既存 `ddg_instant_answer` |
| 注入 | `[web_search_prefetch]` + `[Gateway directive]` — 結果をそのまま引用可、無いときは「見つからへん」 |
| 記憶 | 任意 `http_remember`（category=observation） |
| テスト | `test_web_search_prefetch.py` — 松本市クエリは **空でも honest** |

**受け入れ**: 「調べて」で CC WebSearch が呼ばれない。compose に prefetch ブロックが載る。

**限界**: DDG Instant では松本市様式 URL は **まだ出ない**（既知）。

### WS-2b — URL 付き検索バックエンド（中〜大）

| 候補 | 長所 | 短所 |
|------|------|------|
| DDG HTML / `duckduckgo-search` | 追加 API キー不要、URL 返る | 利用規約・ブロック・日本語行政弱い |
| Brave Search API | 安定、URL+snippet | API キー |
| Google Programmable Search | 日本語・行政に強い | キー + エンジン設定 |

**推奨（ma-home）**: まず **Brave または DDG HTML** をスパイク → 松本市クエリで `city.matsumoto.nagano.jp` が top3 に入るか確認 → 採用。

**注入形式**:

```text
[web_search_prefetch]
query=松本市 地域生活支援事業 日中一時 請求様式
1. https://www.city.matsumoto.nagano.jp/soshiki/61/194124.html — 地域生活支援事業（事業者向け）…
2. …
[/web_search_prefetch]
```

**受け入れ**: 上記クエリで **1 件目に実ページ URL** が prefetch に含まれる（回帰テストはネット依存なら `@pytest.mark.integration`）。

### WS-2c — メッセージ内 URL の gateway 取得（中）

| 項目 | 内容 |
|------|------|
| 検出 | `https?://` URL を 1〜2 件まで（同一メッセージ） |
| 取得 | `httpx` + `readability` または `trafilatura` 相当（HTML → テキスト、max 8k 字） |
| 注入 | `[url_prefetch] url=… excerpt=… [/url_prefetch]` |
| 契約 | **excerpt に無いことは推測で述べない**（補助金/委託の区別は excerpt にあれば可） |
| 失敗 | status=failed → 「ページ開けへんかった」 |

**受け入れ（まー実例）**: 松本市 URL 貼付ターンで prefetch に「日中一時支援（補助金）」「（委託）」の語が excerpt に含まれる。含まれなければこよりは「中身まだ確認できてへん」と言う。

### WS-3 — CC ツール無効化（小）

- `claude_permissions` / native chat: `WebSearch` off（`web_search` prefetch 有効時）
- stable append: memory MCP recall 禁止と同様、CC WebSearch 禁止を明記

### WS-4 — persona export 除外（低）

- 捏造 Sources 付き assistant ターンを export フィルタから除外

---

## 6. plan / compose 契約

`plan_response` または stable append に追加:

- `[web_search_prefetch]` / `[url_prefetch]` があるとき: **その内容だけ**を根拠に答える
- 根拠が無いとき: 「わからん」「まーに URL 教えてもらえたら読める」
- **`Sources:` ブロックを自発生成しない**（prefetch に URL リストがある場合のみリンク可）

---

## 7. 実装タッチポイント（予定）

| ファイル | 変更 |
|----------|------|
| `gateway/user_intent.py` | `wants_web_search`, URL 抽出 |
| `gateway/web_search.py` | `search_with_urls()`（2b）, `fetch_url_excerpt()`（2c） |
| `gateway/search_prefetch.py` | 新規 — `see_prefetch` 同型 |
| `gateway/social_chat.py` | intercept 内で prefetch 合成 |
| `gateway/native_chat_router.py` | router でも intercept 経由なら追加不要 |
| `services/llm.py` | GATEWAY_STABLE_APPEND 契約 |
| `static/chat-markdown.js` | WS-1 |
| `tests/test_web_search_prefetch.py` | 新規 |

---

## 8. 検証シナリオ（手動）

1. 「松本市 地域生活支援事業 日中一時 請求様式 どこ」→ prefetch に市の URL **または** 正直に見つからん
2. まーが正しい URL を貼る → excerpt に補助金/委託の記述 → こよりがそれを引用
3. 空結果 → Sources なし・電話を勧めるだけの長文を **出さない**（短く）

---

## 9. 実装順（合意 2026-06-23）

1. **WS-1 + WS-3**（捏造停止・CC ツール無効化）
2. **WS-2a** → **WS-2b** → **WS-2c**（会話検索 → URL 検索 → URL 貼付読取）
3. **GAPI**（Calendar / Drive）— 上記完了後
4. WS-4（persona export 除外・任意）

**MEM-5j** の backlog 項目は WS-1〜4 をこの doc に集約する。
