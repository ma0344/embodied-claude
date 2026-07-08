# DOC-READ — 長文書の読解・議論（設計）

**合意**: 2026-07-07（まー — 自著 PDF 67p / 77,054 字を「議論・深掘り」したいのが契機）
**状態**: 📋 設計 + **A/B/C 実装済**（2026-07-07）· **D 実装中**（2026-07-08）— E は未着手
**親**: [architecture/cognitive-layers.md](../architecture/cognitive-layers.md) · [architecture/mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)
**関連**: [ops/ws-2-conversation-web-search.md](../ops/ws-2-conversation-web-search.md)（WS-2d PDF 抽出＝この基盤の bytes/path 入口） · [tracks/mem-8h-memory-bridge.md](./mem-8h-memory-bridge.md)（cue 駆動想起＝C の retrieval と同型） · [architecture/mem-pipeline.md](../architecture/mem-pipeline.md)（Dreaming＝B の要約 job）

---

## 1. 問題

WS-2d で PDF テキスト抽出はできた（[ws-2 § WS-2d](../ops/ws-2-conversation-web-search.md#ws-2d--pdf-抽出実装済-2026-07-07)）。だが用途が二つに割れる:

| | 例 | 特徴 |
|--|-----|------|
| **短い根拠 excerpt**（WS-2d 既存） | 「この URL/PDF に何書いてある？」 | 1問1答・query-aware で一部抜けば足る |
| **長文書との議論**（本 track） | まーの自著 67p を俯瞰＋深掘り／会話中に論文を読ませる | **全文はコンテキストに載らない**・継続対話・想起が要る |

**核心の制約**: 日本語 77,054 字 ≒ **6〜10 万トークン**（gemma tokenizer 概算）。ローカル gemma-12b の実効コンテキストに **一冊まるごとは載らない**。上限を上げても解決にならない（載らないから）。

**人間の読書に倣う**: 全文を頭に置いて語る人はいない。**要点の地図を持ち、必要な章を読み返す**。これは まーが前に言った「人間も全部は覚えてへん・違いに気づいた所だけ記銘、あとは想起」と、MEM-8h の cue 駆動 bridge に地続き。

---

## 2. 二つのモード（設計は一本）

| モード | 用途 | 前処理 | 永続 | latency |
|--------|------|--------|------|---------|
| **BOOK**（まーの自著等） | 継続議論・深掘り | **重い一回きり**（分割＋章要約＋記憶定着） | ✅ session 跨ぎ | 前処理はバックグラウンド |
| **PAPER**（会話中に論文/資料を即読み） | その場の議論 | **軽量・即時**（分割のみ／要約は省略可） | ❌ 既定は session-scoped（明示で BOOK 昇格） | **会話中なので速さ優先・非同期** |

**共通の背骨**: `分割(A) →（地図 B）→ cue 駆動 retrieval(C)`。差は「B をやるか」と「記憶に残すか(D)」だけ。だから **一本のパイプラインの深さ違い** として作る。

---

## 3. 認知層への割り当て（cognitive-layers 準拠）

| 層 | 役割 | この track では |
|----|------|----------------|
| **感覚 / 前処理（無人格・deterministic）** | fitz 抽出 · chunk 分割 · doc_id · index · （将来 embedding） | A。人格を通さない。regex/コードでよい機械的境界 |
| **前頭葉 / Stage（LLM）** | 章要約 · 話題/kw 抽出 · query→chunk 選択 | B の要約、C の retrieval 判断 |
| **表層** | 議論そのもの | C の応答 |
| **記憶（MEM-8）** | 地図 gist=L2 · 原文 chunk=L3 参照 · まーの思想=self-narrative/relationship | D |

**regex 方針**: chunk 境界・doc_id・path・PDF 判定＝**deterministic OK**。話題/kw 抽出・要約・retrieval の意味判断＝**e4b / Stage / embedding**（regex で人語の意味を取らない）。→ [README § regex](../README.md#regex-を使う判断基準)

---

## 4. パイプライン

### A — 分割 & インデックス（ingest / 両モードの基盤）

```
PDF(bytes or path)
  → pdf_extract（WS-2d 再利用。ページ単位 text）
  → chunk 化（優先順）
       ① 構造 TOC あり: fitz get_toc()（PDF ブックマーク）で章/節境界
       ② TOC 無いが目次ページあり: 目次テキストを見出し辞書化 → 本文で行頭一致を章境界に（★下記実測で採用）
       ③ どちらも無い: 固定長 ~1500–2000 字 + overlap（数百字）
  → index 保存: doc_id / chunk_id / page_start,end / heading / text / char_count
```

**② の要点**（regex 方針に合致）: 見出し regex を汎用列挙するのは危険（本ごとに違う・終わらない）。代わりに **その文書の目次ページから見出し文字列を取り出して辞書化 → 本文で完全一致**。＝限定語彙の deterministic マッチ（[README § regex](../README.md#regex-を使う判断基準) の「限定語彙・DB」向き）。目次の構造化自体は前頭葉/Stage に任せてよい。

- **doc_id** = 内容ハッシュ（同一 PDF は再 ingest しない＝冪等）。保存先 `~/.claude/presence-ui/docs/{doc_id}/`。
- store は JSONL か SQLite（既存 memory-mcp が SQLite なので合わせる案が有力）。
- **無人格**: ここまでは fitz とコードだけ。LLM を通さない。

### B — 通読要約「本の地図」（map / BOOK モードのみ）

```
各 chunk → gemma で こよりの言葉の要約（3–5 行）
  → 章 gist を束ねる
  → map: 全体要約(1段落) + 目次 + 章ごと gist（数千字 = 常時コンテキストに載るサイズ）
```

- コスト大（67p ≒ 40 chunk × 要約）→ **バックグラウンド job**。tick の合間 or 明示コマンド。**Dreaming 経路**（[mem-pipeline](../architecture/mem-pipeline.md)）と同居させるのが自然。
- PAPER モードは B を**スキップ**（単発なので地図まで作らない）か、超軽量（全体 1 段落だけ）に留める。

### C — 議論（retrieve / inject / 両モード）

```
まー発話
  → 話題/kw 抽出（前頭葉。MEM-8h bridge_topic_keywords と同型）
  → chunk 選択
       v1: キーワード/BM25 風スコア（select_excerpt の延長・embedding 不要）
       v2: embedding 近傍（ローカル embed model 前提・後追い）
  → [doc_context] tier 注入
       - BOOK: 本の地図（常時） + 該当 chunk 1–3 件（query 依存）
       - PAPER: 全体軽要約 + 該当 chunk 1–3 件
  → 応答（WS-2d と同契約: chunk に無いことは推測で述べない・捏造禁止）
```

- 予算管理: chunk 数・字数 cap（コンテキスト予算から逆算）。地図＋chunk が tier cap を超えない。
- 注入 directive は WS-2d の `format_url_prefetch_block` 契約を踏襲（「excerpt/chunk のみ根拠」「無ければ正直に」）。

### D — 記憶定着（ongoing / BOOK モード）

**合意（2026-07-08 · まー）**: **A + B の二段**。青空拡張を見据え、「まだ話してない本も記憶に入る」は A のメリット（自動 ingest ＋ まー依頼の両方で bridge から引ける）。

| 段 | タイミング | 書く内容 | layer（Linksee 相当） | category（memory-mcp） |
|----|-----------|----------|----------------------|------------------------|
| **A** | `doc-read map` 完了直後（自動） | 地図 gist + `doc_id` + タイトル/別名。全文 chunk は入れない | `context`（所持知識） | `memory` |
| **B** | C 初回発火（`prefetch_doc_context` が doc を解決して `[doc_context]` を組めた**初回のみ**） | 「まーとこの本について話した」+ きっかけ発話 + `discussed_at` | `learning`（経験） | `conversation` |

**重複防止**: `registry.json` の各 doc に `memory_map_id` / `memory_discussed_id` / `memory_map_at` / `discussed_at` を保持。A は map 済みなら再 remember しない（map 再生成時の refresh は将来フラグ）。

**MEM-8h bridge**: gist 先頭に `title` / `aliases` / `doc_id` を機械的に載せ、bridge の kw→recall と同型（意味抽出は regex しない）。本と無関係な雑談でも cue が地図 gist に当たれば dated gist が surface に載る。

**まーの著作**: self-narrative / relationship 向けに「まーはこういう思想の本を書いた人」が自然に効く（単なる資料ではない）。

**L3 原則**: 原文 chunk は `chunks.jsonl` 保持。memory には**参照（doc_id）と gist だけ**。全文 remember はしない。

**青空への布石（将来）**: 同じ A/B 契約を青空読書に流用 — A＝節読了・地図化時、B＝まーとその作品について話した初回。`doc_id` は作品 ID＋しおり等で足す。

**env**: `PRESENCE_DOC_MEMORY`（既定 ON）· `PRESENCE_DOC_MEMORY_GIST_MAX_CHARS`（gist 上限、既定 3500）

---

## 5. 本番運用フロー（会話中に論文を読ませる＝PAPER）

```
まー「この論文読んで、議論しよ」＋ URL or "C:\…\paper.pdf"
  → intercept（既存 url_prefetch 経路の延長）
  → detect: PDF 検出（WS-2d）＋「長文議論 intent」（読んで/議論/深掘り + 資料/論文/本/PDF）
  → ingest(A) を即時実行（キャッシュ: 2回目以降は doc_id hit で即）
       ・大きい PDF は初回が重い → progress_event「読み込んでる…」・非同期
  → retrieve(C): まーの問い or 冒頭 → 該当 chunk
  → [doc_context] 注入 → 応答
  → 単発は session-scoped（定着しない）。「覚えといて」で BOOK へ昇格（B+D 起動）
```

**WS-2d との棲み分け**（重要）:

| 判定 | 経路 |
|------|------|
| 短い・1問1答・根拠 excerpt で足りる | **WS-2d 既存**（そのまま） |
| 長文・議論/深掘り intent・継続 | **DOC-READ**（ingest→retrieve） |

intent 判定は Stage/e4b 側（「読んで」「議論」「深掘り」＋「論文/本/資料/PDF」）。regex は PDF/URL/path の**機械的検出ゲートまで**。

---

## 6. env / storage（設計・予定）

| 変数 | 用途（案） |
|------|-----------|
| `PRESENCE_DOC_STORE_DIR` | index/chunk/map 保存先（既定 `~/.claude/presence-ui/docs`） |
| `PRESENCE_DOC_CHUNK_CHARS` | 固定長 chunk サイズ（見出し無し時） |
| `PRESENCE_DOC_CHUNK_OVERLAP` | overlap 字数 |
| `PRESENCE_DOC_MAP_ENABLED` | B（章要約）を回すか |
| `PRESENCE_DOC_RETRIEVE_MAX_CHUNKS` | C で注入する chunk 上限 |
| `PRESENCE_DOC_EMBED_MODEL` | v2 embedding モデル（未定・v1 は keyword） |

---

## 7. フェーズ

| # | 内容 | モード | 依存 | 状態 |
|---|------|--------|------|------|
| **A** | ingest: chunk 分割 + index（fitz get_toc / 目次辞書 / 固定長）· 冪等 doc_id | 両 | WS-2d | ✅ 2026-07-07 |
| **B** | map: 章要約「本の地図」（CLI `doc-read map` · LM Studio） | BOOK | A | ✅ 2026-07-07 |
| **C** | retrieve + `[doc_context]` 注入 + 議論（v1 keyword+bigram · cue/sticky/title 解決 · chat 配線） | 両 | A（B は BOOK 時） | ✅ 2026-07-07 |
| **D** | 記憶定着 A（map→remember）+ B（初回議論）+ MEM-8h bridge | BOOK | C, MEM-8h | 🔥 2026-07-08 |
| **E** | 本番: 会話中 PDF/論文 on-demand + intent 検出 + cache | PAPER | A,C | 📋 |
| **F**（opt） | embedding retrieval へ昇格（v2） | 両 | C | 📋 |

**最短の一歩**: A+B（分割＋章要約）だけで「本の地図」ができ、今の「冒頭しか読めてない」状態からは激変する。C の自動 pull は後追い。

---

## 8. 決めきってない（確認・実測待ち）

1. ~~**gemma の実効コンテキスト長**~~ → **決着: ctx = 87,085 token**（2026-07-07 まー設定）。§10 で予算化。
2. **embedding をローカルで持てるか**（LM Studio に embed model を置けるか）— v1 は keyword、v2 で embedding。無ければ BM25 風で当面回す。
3. ~~**chunk 境界**~~ → **決着: 自著は構造 TOC 無し・目次ページ有り** → A-② 採用。§10。
4. ~~**BOOK/PAPER の昇格 UX**~~ → **BOOK 定着は A+B 自動**（2026-07-08）。PAPER の「覚えといて」昇格は E で別途。
5. **store**: SQLite（memory-mcp と統一）か JSONL か。

---

## 10. 実測（2026-07-07 · まー自著 PDF）

対象: `h:\マイドライブ\本\本文テキスト.pdf`（印刷確認用をテキスト PDF に変換）。fitz で解析:

| 項目 | 値 |
|------|-----|
| ページ数 | **65**（ビューア表記 67 とは別カウント） |
| 総文字数 | **77,190 字** / 平均 1,188 字・頁（580〜1,386） |
| フォント | `CIDFont+F1`（Type0 / Identity-H · subset） |
| producer | Microsoft: Print To PDF |
| 構造 TOC | **無し**（`get_toc()` 空） |
| テキスト目次 | **3 ページ目に有り** |
| 抽出品質 | **完全**（ToUnicode 効。※端末 cp932 では化けるが UTF-8 出力は正しい＝**表示問題のみ、データは正**） |

**章構成（目次より）**: はじめに（田中康雄）／プロローグ／第一章 つい"障害に甘えてしまう"僕ら／第二章 本人のものは本人のもの／第三章 本人も支援者もハッピーでありたい！ ＋ 各章に「エピソード①〜⑦」「山口×田中のキャッチトーク①②」＋小見出し多数。タイトル『ＡＤＨＤの僕がグループホームを作ったら、モヤモヤに包まれた』。

**chunk 戦略（確定）**: A-②。3 ページ目の目次を辞書化 → 本文で「第一章／第二章／第三章／プロローグ／はじめに／エピソード①…／…キャッチトーク…」の行頭一致を章境界に。章＝chunk（大章は予算で再分割＋overlap）。

**ctx 予算（87,085 token）**:

- 日本語 77,190 字 ≒ 本文だけで **7〜8 万 token 規模**。技術的には「本文まるごと」もギリ載るが、**毎ターン KV に載せると遅延・cache 破壊**で会話にならない → **全文常時は却下**。
- 採用: **本の地図 gist（〜3–5k token・常時）＋ 該当章 chunk 1–2 個（各 1.5–2 万 token）＋ 会話 ＋ SOUL**。ctx 87k なら該当章 2 個でも余裕。
- ＝ §4 の「地図＋cue 駆動で章 pull」がこの実測でも最適と確認。

**注意**: 抽出テキストを扱う経路（ログ・デバッグ表示）は **UTF-8 前提**。Windows 端末の cp932 で直接 print すると化ける／`UnicodeEncodeError` になる（データは壊れていない）。

**A/B 実装（2026-07-07）**:

- コード: `presence_ui.services.doc_read` · `presence_ui.cli.doc_read` · `presence_ui.services.lm_client`（gateway 非依存 LM 呼び出し）
- CLI: `doc-read ingest <path>` → `doc-read map <doc_id>` → `doc-read show <doc_id>`
- 章検出: 短い見出し行（≤40字）+ **TOC ページ除外**（`目次` 語 or 短マーカー≥2本/頁）。Print-to-PDF の連続フローでも実測で 13 chunk に分割成功。
- まー自著の実測: `doc_id=23000cc4d7a222f8` · はじめに→第一章→第二章→第三章→エピローグ→おわりに · map.md 生成 ~1分（13 chunk + 全体要約）
- store: `~/.claude/presence-ui/docs/{doc_id}/`（meta.json · chunks.jsonl · map.md）

**内容メモ**: ADHD 当事者（山口さん）がグループホームを立ち上げた経験を、監修（田中康雄）・編集（中野さん）と作った本。まーの [ADHD body double 構想](../backlog-koyori.md#adhd-body-double構想--2026-07-07) と地続き。BOOK 定着時は self-narrative / relationship への効かせ方に配慮（親密・当事者性の高い素材）。

**C 実装（2026-07-07）**:

- コード: `presence_ui.services.doc_read`（registry `register_doc`/`set_doc_title`/`active_doc_id`/`resolve_doc_by_text` · retrieve `query_terms`/`match_terms`/`select_chunks`/`load_map`）· `presence_ui.gateway.doc_prefetch`（`resolve_doc_for_turn` · `build_doc_context_block` · `prefetch_doc_context_for_turn`）
- 配線: `native_chat_router` / `chat_stream` が url_prefetch と同列で `doc_prefetch=` を intercept に渡す（`social_chat` に新チャンネル追加、`enriched_message` 末尾に `[doc_context]` 追記）。
- **継続の二層**:
  - session 内 = **sticky TTL**（`PRESENCE_DOC_STICKY_TURNS`、既定3）。cue/title で開き、cue 無しでも数ターン継続 → decay（「終わり方」）。
  - session 跨ぎ = **registry のタイトル/エイリアス一致**（`resolve_doc_by_text`）で「この間の〇〇の本の続き」を復帰。doc_id は内容ハッシュで不変。
- **発火**（`resolve_doc_for_turn` の reason）: `title`（タイトル/別名一致）＞ `cue`（限定語＋active/sticky book）＞ `sticky`（継続）＞ `none`。cue 語は最小限（本/著作/続き/章/…）＝ deterministic ゲート。
- **タイトル**: PDF メタは `!L` で当てにならん → `doc-read title <id> "…" --alias …` で人手登録（「〇〇の本」解決の索引）。
- retrieve は **keyword＋JP バイグラム**。助詞込みラン（「寄り添いについて」）でも bigram で「寄り添い」章にヒット（実測: 「寄り添い/責任」→ 第二章・第三章を選択）。embedding 不要（v2=F で昇格）。
- 契約: WS-2d 同型 directive。「map/chapter だけを根拠、無い細部は正直に『その章はまだ手元にない』」。
- env: `PRESENCE_DOC_CONTEXT` / `PRESENCE_DOC_STICKY_TURNS` / `PRESENCE_DOC_RETRIEVE_MAX_CHUNKS` / `PRESENCE_DOC_MAP_MAX_CHARS` / `PRESENCE_DOC_CHUNK_MAX_CHARS`
- store: `docs/registry.json`（active + title/alias）· `docs/sessions.json`（session→sticky）

**次（D）**: §4 D 参照。コード: `presence_ui.services.doc_memory` · `build_map` 完了時に A · `doc_prefetch` 初回発火時に B。

**D 実装（2026-07-08）**:

- コード: `presence_ui.services.doc_memory`（`gist_for_memory` · `remember_book_map` · `remember_book_discussed`）
- A: `build_map` / `doc-read map` 完了直後に `remember_book_map(doc_id)`
- B: `prefetch_doc_context_for_turn` が `[doc_context]` を組めた**初回のみ** `remember_book_discussed(doc_id, cue=message)`
- registry: `memory_map_id` / `memory_discussed_id` / `memory_map_at` / `discussed_at`
- env: `PRESENCE_DOC_MEMORY` / `PRESENCE_DOC_MEMORY_GIST_MAX_CHARS`

---

## 9. 既存資産の再利用（車輪の再発明を避ける）

- **WS-2d `pdf_extract`**: bytes/path→text・allowlist・上限・scanned 検出をそのまま A の入口に。
- **`url_prefetch` の block/directive 契約**: C の `[doc_context]` 注入と捏造禁止 directive に流用。
- **MEM-8h `bridge_topic_keywords` / recall**: C の retrieval と D の想起に同型適用。
- **mem-pipeline Dreaming**: B の要約バッチ job の実行枠に。
