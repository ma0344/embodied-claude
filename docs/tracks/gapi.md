# GAPI — Google Calendar / Drive

**状態**: ✅ **prep-1/2 完了**（ma-home CLI smoke OK）· 📋 **prep-3 待ち**（router 実線は意図的に未接続）  
**関連**: [ws-2-conversation-web-search.md](../ops/ws-2-conversation-web-search.md)、[open-loops-reminders.md](../architecture/open-loops-reminders.md)、[cognitive-layers.md](../architecture/cognitive-layers.md)、[ops/gapi-setup.md](../ops/gapi-setup.md)

---

## 下準備フェーズ（2026-06-27）

OAuth / ポリシー / Google API を **CLI smoke で先に通す**。会話経路（`native_chat_router`）への注入は **prep-3** で別コミット。

| Prep | 内容 | 状態 | コミット / 入口 |
|------|------|------|-----------------|
| **prep-1** | OAuth consent · `gapi-policy.toml` walk-up · today+tomorrow **list** · `[calendar_prefetch]` 整形 | ✅ ma-home | `6793066` · `uv run gapi-calendar-smoke --prefetch` |
| **prep-2** | `calendar.events` · policy `allow_create/update` · **create + patch** smoke（`[gapi-smoke]`） | ✅ ma-home | `573e370` · `uv run gapi-calendar-write-smoke` |
| **prep-3** | `native_chat_router.py` へ `[calendar_prefetch]` 注入 · `PRESENCE_GAPI_ENABLED=1` | 📋 **未着手** | [§配線 要検討](./gapi.md#配線--要検討2026-06-27) を先に詰める |

**いま触らないもの（合意）**

- router / gateway への **実線接続** — prep-3 まで `PRESENCE_GAPI_ENABLED=0` のまま
- 会話からの Calendar **書込**（GAPI-7 gateway direct）— 読取 E2E の後
- delete API — v1 非公開のまま

**コード位置**: `presence-ui/src/presence_ui/gapi/`（`auth` · `policy` · `calendar_client` · `calendar_writes` · `cli`）

---

## 合意（2026-06-27 — まー）

| 項目 | 決定 |
|------|------|
| **読み/書き** | **Calendar / Drive とも書込を許可する方針**。実装は **読取から**（Calendar 読 → Calendar 書 → Drive 読 → Drive 書） |
| **認証** | **OAuth（まー個人）** — refresh token は git 外 |
| **Calendar 読** | **primary** + **共有カレンダーをポリシーで追加** · prefetch **今日+明日** |
| **Calendar 書** | 予定の **作成・変更**（カレンダーごとにポリシーで許可）— **Phase 1.5（読取 E2E の後）** |
| **Drive 読** | 「〇〇のことが書いてある資料はある？」 |
| **Drive 書** | 「〇〇についてのドキュメントを GDrive に作っておいて」— **Phase 2b** |
| **Prefetch 窓** | **今日 + 明日**（日付範囲）。件数切り捨ては主制約にしない |
| **プライバシー** | 第三者名・場所入り予定も **発話・memory に載せて OK** |
| **第一 E2E** | **Calendar 読**「今日の予定は？」→ 続けて **Calendar 書** |

---

## 北極星シナリオ

### Calendar（GAPI-2 — 第一 E2E）

| | 台詞 |
|---|------|
| **まー** | 「今日の予定は？」 |
| **いま** | 訓練データ・曖昧な一般論 |
| **期待** | 「14時に〇〇、明日は△△やな」— **Calendar prefetch 根拠のみ** |

未接続時: 「カレンダー繋がってへん」— 捏造しない（WS-1 正直化と同型）。

**prep-1 で確認済**: CLI `--prefetch` が `[calendar_prefetch]` を出力。**prep-3 で router 注入後**に会話 E2E。

### Calendar 書込（GAPI-7 — Phase 1.5）

| | 台詞 |
|---|------|
| **まー** | 「来週火曜15時に〇〇の会議、カレンダー入れといて」 |
| **期待** | gateway が `events.insert`（許可カレンダー）→ 「入れたで、リンクは…」— **API 結果を根拠** |

| | 台詞 |
|---|------|
| **まー** | 「明日14時の予定、16時にずらして」 |
| **期待** | prefetch で対象特定 → `events.patch` → 変更後を短く報告 |

**OL / commitment との接続（任意）**: 会話で「10時にリマインド」→ commitment と **並行**で Calendar イベントを作るかは GAPI-3 / 別判断。v1 は **明示のカレンダー操作発話**のみ。

書込は **OAuth スコープ追加（再 consent）** + ポリシー `allow_create` / `allow_update` + `evaluate_action`（busy / quiet 考慮）。**削除は v1 非対応**（誤削除リスク）。

**prep-2 で確認済**: CLI create + patch（`[gapi-smoke]`）。**会話 gateway 配線は prep-3 / GAPI-7 本線で別途**。

### Drive 読取（GAPI-4 — Phase 1b）

| | 台詞 |
|---|------|
| **まー** | 「 cardiovascular AI のことが書いてある資料、Drive にある？」 |
| **期待** | `[drive_prefetch]` に候補ファイル名 + リンク + 要約断片 → 表層が根拠付きで答える |

### Drive 書込（GAPI-6 — Phase 2、未 ID 化）

| | 台詞 |
|---|------|
| **まー** | 「〇〇についてのドキュメントを GDrive に作っておいて」 |
| **期待** | gateway が Docs 作成（スコープ内フォルダ）→ リンク返却 → salient remember |

書込は **OAuth スコープ追加** + `evaluate_action` + 明示確認（v1 は下書き/限定フォルダ）。

---

## 原則

| 原則 | 内容 |
|------|------|
| 読取先行 | Phase 1 = Calendar/Drive **読取**。書込は Calendar → Drive の順 |
| gateway 直実行 | WS-2 / `search_prefetch` と同型 — LLM に Google ツール名を選ばせない |
| 境界 | 全 Drive ではなく **ポリシーで許可したカレンダー・フォルダ** |
| 認証 | OAuth（まー）。トークン `~/.claude/google/` 等 git 外 |
| 記憶 | 全文 LTM 化しない。salient + OL/commitment（GAPI-3 は任意） |
| プライバシー | 2026-06-27 合意: 予定の人名・場所は **載せて OK** |
| **下準備** | CLI smoke で API/ポリシーを先に通す · **router 実線は prep-3 まで切る** |

---

## Prefetch 窓 — 日付 vs 件数

**合意: 今日 + 明日（日付範囲）を主軸**

| 方式 | 評価 |
|------|------|
| **日付範囲**（採用） | 「今日の予定は？」の mental model と一致。夕方の重要予定を午前の件数上限で落とさない |
| **件数上限のみ**（不採用） | 忙しい日に arbitrary 切り捨て。OL「当日 open」の文脈ともズレやすい |

**安全弁（実装時）**: 件数ではなく **`max_prefetch_chars`**（例 4000）で LM コンテキストを保護。超過時は gateway が `status=truncated` と明示し、表層に「予定多すぎるから要点だけ」と正直に言わせる。

**timezone**: `socialPolicy [global] timezone = "Asia/Tokyo"` — 今日/明日の境界はここ基準。

### Prefetch ブロック例

```text
[calendar_prefetch]
range=today,tomorrow
timezone=Asia/Tokyo
status=ok
calendars=primary,team-shared@group.calendar.google.com
--- events ---
2026-06-27T14:00+09:00 | 会議タイトル | 場所
2026-06-28T10:00+09:00 | …
[/calendar_prefetch]
```

---

## アーキテクチャ

```
まー発話 / tick
  → intent（calendar_query | calendar_create | calendar_update | drive_search | drive_create）
  → 読取: gateway prefetch → [calendar_prefetch] / [drive_prefetch]
  → 書込: gateway direct（Google API）→ 結果を表層へ（prefetch ではない）
  → native chat enriched message → 表層 LM
  → remember（salient）+ commitment / OL（任意）
```

**注入点**: `native_chat_router.py` — `web_search_note` / `url_note` と同列（**prep-3** · **配線詳細は下 §要検討**）。

**WS との関係**

| データ | 経路 |
|--------|------|
| 公開 Web / 行政 PDF | WS-2b/c |
| Drive 内ドキュメント | GAPI-4 |
| 会話の外部事実（地震等） | WS-5（将来） |

---

## 配線 — 要検討（2026-06-27）

prep-1/2 は **API・ポリシー・CLI** まで。**いつ・どこに載せるか**は prep-3 の前に決める。現時点は **未決定の論点を積む**（実装は先に進めない）。

### 問題の分解

| 論点 | 質問 | 現状 |
|------|------|------|
| **トリガー** | この発話で Calendar API を叩くか？ | 要検討（下 L0–L3） |
| **窓** | 叩くなら何日分取るか？ | policy 既定は today+tomorrow · **発話依存の窓は未実装** |
| **注入先** | compose vs enriched user message | WS-2 **たたき台** = router prefetch → user message 末尾 · **確定していない** |
| **書込** | prefetch と別レーンで gateway direct | 方針のみ · 会話配線未 |

**毎ターン API は叩かない** — WS-2 `search_prefetch` と同型が第一候補（未確定）。

### compose の `calendar_anchor` との違い

compose には既存の **日付錨** がある（`social_core.date_resolution.calendar_anchor_line` — 「今日は何月何日か」だけ）。**Google Calendar の中身ではない**。

| 層 | 内容 | タイミング |
|----|------|------------|
| compose anchor | `Calendar today (Asia/Tokyo): …` | 毎ターン（既存） |
| GAPI prefetch | 実イベント一覧 `[calendar_prefetch]` | **要検討** — intent 時のみが第一候補 |

### まー例 — 読取トリガー（要検討 · L0 たたき台）

| 例 | 想定窓 |
|----|--------|
| 明日は予定あった？ | 明日 1 日 |
| 〇月〇日は何か予定があったっけ？ | その日 |
| 〇月〇日は何してたっけ？ | その日（**calendar のみ vs memory recall も** — 未決） |
| 来週の予定ってどうなってたっけ？ | 来週月〜日 |
| 今日の予定は？ | 既定 today+tomorrow（policy） |

→ prep-1 CLI は **today+tomorrow 固定**。上記の「来週」「〇月〇日」は **発話から窓を解決**する実装が別途必要。

### 書込トリガー（要検討 · L0 たたき台）

| 例 | API |
|----|-----|
| カレンダーの〇月〇日〇時〇分に〇〇を入れて | `events.insert`（prefetch 不要 · 衝突確認は将来） |
| 明日14時の予定、16時にずらして | read で特定 → `events.patch` |

### トリガー層（要検討）

| 層 | 内容 | 例 | v1 |
|----|------|-----|-----|
| **L0** | 明示キーワード + 日付式 | 予定 / カレンダー / スケジュール + 今日・明日・来週・〇月〇日 | **第一候補** |
| **L1** | 日付 + 行動語（「予定」なし） | 〇月〇日何してた / 来週どうなってる | 要検討 |
| **L2** | 空き・都合 | 空いてる / 会える / 忙しい | 要検討（today+tomorrow 窓と相性良） |
| **L3** | GW interpret フラグ | `calendar_relevant: true` のみ | 任意 · 後回し可 |

**L0 ルール案（未確定）**: `予定` `スケジュール` `カレンダー` · 相対日 `今日` `明日` `来週` · 絶対日（`date_resolution` / ja_timex 再利用）。

### v1 たたき台フロー（要検討 · 未合意）

```
発話
  → L0/L1 で calendar_read_intent?
       No  → API しない（compose calendar_anchor のみ）
       Yes → 発話から date_range 解決 → gateway fetch → [calendar_prefetch]
  → compose / plan → enriched user message 末尾（WS-2 同型が第一候補）
```

### その他 — 要検討リスト

- [ ] **注入先**: router prefetch のみ vs compose 常時要約 vs ハイブリッド
- [ ] **窓**: policy 既定 vs 発話パース（来週 / 特定日）— `social_core.date_resolution` 再利用
- [ ] **L2** を v1 に含めるか（空いてる / 会える）
- [ ] **キャッシュ TTL** — 同一セッション intent 連打時（例 5 分）
- [ ] **失敗時** — `status=error` ブロック vs honesty directive
- [ ] **lite モード** — `truncate_lite_turn_delta` と prefetch の優先
- [ ] **「何してたっけ」** — GAPI vs memory recall の分担
- [ ] **書込前 read** — 同時間帯衝突確認をするか
- [ ] **OL5 / open loops** — prefetch と compose 上で並べるか（GAPI-3 まで待つか）
- [ ] **quiet / evaluate_action** — 読取は常時 OK？ 書込のみ boundary？

---

## 実装 ID

| ID | 内容 | Phase | 状態 |
|----|------|-------|------|
| **GAPI-0** | ポリシー — カレンダー/Drive スコープ・読書権限・prefetch 窓 | 0 | ✅ `policy.py` + example TOML |
| **GAPI-1** | OAuth + refresh + `GOOGLE_*` env | 0 | ✅ prep-1 · ma-home consent OK |
| **GAPI-2** | Calendar **読取** prefetch（today+tomorrow） | 1 | 📋 CLI ✅ · **router 未**（prep-3） |
| **GAPI-5** | `koyori/status` 接続状態 | 1 | 未 |
| **GAPI-7** | Calendar **書込**（create / update） | 1.5 | 📋 CLI ✅ · **gateway 会話未** |
| **GAPI-4** | Drive 読取・検索・要約 | 2a | 未 |
| **GAPI-6** | Drive 書込（Docs 作成） | 2b | 未 |
| **GAPI-3** | OL / commitment / Calendar 突合・連携 | 3 | 未 |

**実装順**: GAPI-0 → GAPI-1 → **GAPI-2 + GAPI-5** → **GAPI-7** → GAPI-4 → GAPI-6 → GAPI-3

**次の一手**: **§配線 要検討** を詰める → **prep-3**（router 注入）→ 「今日の予定は？」会話 E2E。

---

## GAPI-0 ポリシー

→ [examples/configs/gapi-policy.example.toml](../../examples/configs/gapi-policy.example.toml)  
→ 本番: リポジトリ直下 `gapi-policy.toml`（gitignore · walk-up 検出）

要点:

- `[[google.calendars]]` — `read_events` + **`allow_create` / `allow_update`**（書込 Phase 1.5）
- `[[google.drive_roots]]` — 検索・作成の親フォルダ
- `prefetch_day_range = ["today", "tomorrow"]`
- `max_prefetch_chars = 4000`

---

## Intent 検出（v0 ルール · 要検討）

詳細・層（L0–L3）・まー例 → [§配線 要検討](#配線--要検討2026-06-27)

| intent | キュー例 | Phase |
|--------|----------|-------|
| `calendar_query` | 予定、カレンダー、スケジュール、今日何がある、明日 | 1 |
| `calendar_create` | 入れといて、予定入れて、カレンダーに追加、ブロックして | 1.5 |
| `calendar_update` | ずらして、変更して、時間変えて、リスケ | 1.5 |
| `drive_search` | ドライブ、Drive、資料、探して | 2a |
| `drive_create` | ドキュメントを作って、GDrive に作って | 2b |

v1: GW interpret で `calendar_query` / `drive_search` を WS-5 同型に（任意）。

---

## 認知層

| 層 | GAPI |
|----|------|
| **感覚・身体** | Calendar / Drive API HTTP |
| **前頭葉** | intent ルール、日時パース（`date_resolution` 再利用可）、Drive 要約（任意） |
| **表層** | 読取: prefetch 根拠。書込: **API 結果を受けて**台詞（「入れたで」） |
| **記憶** | salient（例: 「明日10時会議」）— 全文 remember しない |

---

## 関連

- OAuth · smoke 手順: [ops/gapi-setup.md](../ops/gapi-setup.md)
- 全文アーカイブ: [archive § GAPI](../archive/backlog-ma-home-full-2026-06-26.md#gapi--google-calendar--drive合意-2026-06-23)
