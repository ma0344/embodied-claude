# OL Close 朝テスト（ma-home · 2026-06-30）

**順序**: ① この Close テスト → ② [TEMP-C5](../tracks/utterance-anchoring.md#temp-c5--clock--相対時刻アンカー設計--2026-06-29) 実装

**目的**: OL5-b / OL6 / OL7 が **DB で `status=closed`** になるか。表層の「わかってるね」だけでは不合格。

---

## 事前（テスト前夜 or 朝イチ）

### 1. `presence-ui.local.env`

`%USERPROFILE%\.config\embodied-claude\presence-ui.local.env`

```env
PRESENCE_GW_S2_ENABLED=1
PRESENCE_GW_S2_STAGED=1
PRESENCE_CLASSIFIER_MODEL=google/gemma-4-e4b

PRESENCE_OL7_ENABLED=1
PRESENCE_OL7_IMMEDIATE_CONFIDENCE=0.9
```

### 2. 依存パッケージ + 再起動

```powershell
cd C:\Users\ma\src\embodied-claude\presence-ui
uv sync --reinstall-package social-core --reinstall-package relationship-mcp --extra dev
cd C:\Users\ma\src\embodied-claude
.\scripts\restart-presence-ui.ps1
```

LM Studio で **e4b** がロードされていること。

### 3. open loop の確認

```powershell
sqlite3 $env:USERPROFILE\.claude\sociality\social.db "
SELECT loop_id, topic, status,
       json_extract(detail_json,'$.pending_check.trigger') AS pending_trigger,
       json_extract(detail_json,'$.pending_check.asked_at') AS asked_at
FROM open_loops WHERE person_id='ma' AND status='open'
ORDER BY updated_at DESC;"
```

**残っている loop**（例: サッカー `loop_a03a04dfb7`）はそのまま使える。不要なら手動 `closed` か dismiss 発話で掃除。

---

## 判定の共通ルール

| 見る場所 | 合格 |
|----------|------|
| **DB** `open_loops.status` | `closed` |
| `detail_json.kind`（close 後） | `ol5_completion` / `ol6_completion` / `ol7_completion` |
| 表層こより | 口先だけ「終わったね」で DB が open のまま → **不合格** |

`pending_check` の流れ:

1. OL7 **return_signal** → `trigger=ol7_return_signal` · `asked_at` **なし**（candidate）
2. こよりが確認 → `asked_at` あり
3. まーが短答 → close

---

## シナリオ（優先順）

### A — 既存 loop（サッカー · until_completed）

昨夜の loop が open なら:

| # | まー | 期待 |
|---|-----|------|
| A1 | 「見終わった」 / 「試合見終わった」 | **OL5-b または OL7 即 close** · サッカー loop のみ closed |
| A2 | 「ただいま」だけ（試合後の合図） | **pending** → こより「見たん？」→「うん」→ **ol7_completion** |

メモ: `start_at` 無し（C5 前）なので OL6 時刻トリガーは期待しない。

### B — 新規で 1 件作って close（散歩）

| # | まー | 期待 |
|---|-----|------|
| B1 | 「散歩に行く」 | open loop 1 件 |
| B2 | 「ただいま」 | pending **または** 即 close（どちらも可） |
| B2' | （pending なら）こよりの質問のあと「うん、いい感じ」 | closed · `ol7_completion` |
| B3 | 別ターンで B1 から「散歩、行ってきた」 | **OL5-b** · OL7 不要 |

### C — 明示完了（複数 open があっても）

| # | まー | 期待 |
|---|-----|------|
| C1 | 「昼寝する」→（別件）「書類を作る」 | 2 件 open |
| C2 | 「昼寝終わった」 | **昼寝のみ** closed |

### D — no-op（誤 close しない）

| # | まー | 期待 |
|---|-----|------|
| D1 | 「おはよう」（open あり） | close しない · 新 loop も増やさない（GW-S2 greeting） |
| D2 | 「ごちそうさま」（食事系 loop 無し） | close しない |

### E — OL6（時刻あり loop があれば）

`until_phrase` 付き loop（例: 書類15時まで）が **時刻過ぎ** なら:

1. こよりが自然に「終わった？」
2. まー「終わったよ」
3. `ol6_completion`

---

## 記録テンプレ

| シナリオ | 発話 | DB closed? | close_kind | メモ |
|----------|------|------------|------------|------|
| A1 | | | | |
| B2→B2' | | | | |
| … | | | | |

---

## 失敗時の切り分け

| 症状 | 疑うところ |
|------|------------|
| 表層だけ反応 · DB open | OL7 未 enable · ingest 順 · `relationship-mcp` 古い |
| pending にならない | `PRESENCE_OL7_ENABLED` · e4b 落ち · GW-S2 off |
| 確認後も close しない | `mark_loop_check_asked` / `try_ol6_pending_close` · 「うん」が regex に合うか |
| 別 loop が閉じる | 複数 open · 分類器の `close_loop_ids` — DB の `loop_id` を照合 |

ログ: presence-ui コンソールに `OL7 return_signal` / `OL5-b` 周辺。

---

## テスト後

- Close が通った経路を [ol5.md § OL7](../tracks/ol5.md) に ✅ メモ
- 問題なければ **TEMP-C5**（`この後 午前2時` → `start_at`）実装へ → [utterance-anchoring.md § TEMP-C5](../tracks/utterance-anchoring.md#temp-c5--clock--相対時刻アンカー設計--2026-06-29)

```powershell
# 回帰（自動 · 任意）
cd C:\Users\ma\src\embodied-claude\sociality-mcp\packages\relationship-mcp
uv run pytest tests/test_open_loops_reminders.py -q -k "ol5 or ol6 or ol7"
cd C:\Users\ma\src\embodied-claude\presence-ui
uv run pytest tests/test_ol7_flow.py tests/test_ol7_return_signal.py -q
```
