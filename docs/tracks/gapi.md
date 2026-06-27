# GAPI — Google Calendar / Drive

**状態**: 📋 下準備中（GAPI-0 合意 2026-06-27）  
**関連**: [ws-2-conversation-web-search.md](../ops/ws-2-conversation-web-search.md)、[open-loops-reminders.md](../architecture/open-loops-reminders.md)、[cognitive-layers.md](../architecture/cognitive-layers.md)、[ops/gapi-setup.md](../ops/gapi-setup.md)

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

**注入点**: `native_chat_router.py` — `web_search_note` / `url_note` と同列。

**WS との関係**

| データ | 経路 |
|--------|------|
| 公開 Web / 行政 PDF | WS-2b/c |
| Drive 内ドキュメント | GAPI-4 |
| 会話の外部事実（地震等） | WS-5（将来） |

---

## 実装 ID

| ID | 内容 | Phase | 状態 |
|----|------|-------|------|
| **GAPI-0** | ポリシー — カレンダー/Drive スコープ・読書権限・prefetch 窓 | 0 | 📋 草案 |
| **GAPI-1** | OAuth + refresh + `GOOGLE_*` env | 0 | 未 |
| **GAPI-2** | Calendar **読取** prefetch（today+tomorrow） | 1 | 未 |
| **GAPI-5** | `koyori/status` 接続状態 | 1 | 未 |
| **GAPI-7** | Calendar **書込**（create / update） | 1.5 | 未 |
| **GAPI-4** | Drive 読取・検索・要約 | 2a | 未 |
| **GAPI-6** | Drive 書込（Docs 作成） | 2b | 未 |
| **GAPI-3** | OL / commitment / Calendar 突合・連携 | 3 | 未 |

**実装順**: GAPI-0 → GAPI-1 → **GAPI-2 + GAPI-5** → **GAPI-7** → GAPI-4 → GAPI-6 → GAPI-3

---

## GAPI-0 ポリシー（草案）

→ [examples/configs/gapi-policy.example.toml](../../examples/configs/gapi-policy.example.toml)  
→ 本番は `socialPolicy.toml` に `[google]` をマージするか、専用 TOML + walk-up 検出（OL-GATE 同型）

要点:

- `[[google.calendars]]` — `read_events` + **`allow_create` / `allow_update`**（書込 Phase 1.5）
- `[[google.drive_roots]]` — 検索・作成の親フォルダ
- `prefetch_day_range = ["today", "tomorrow"]`
- `max_prefetch_chars = 4000`

---

## Intent 検出（v0 ルール）

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

- OAuth 手順: [ops/gapi-setup.md](../ops/gapi-setup.md)
- 全文アーカイブ: [archive § GAPI](../archive/backlog-ma-home-full-2026-06-26.md#gapi--google-calendar--drive合意-2026-06-23)
