# OL Close 朝テスト（ma-home · 2026-06-30）

**順序**: ① この Close テスト → ② [TEMP-C5](../tracks/utterance-anchoring.md#temp-c5--clock--相対時刻アンカー設計--2026-06-29) 実装

**目的**: OL5-b / OL6 / OL7 が **DB で `status=closed`** になるか。表層の「わかってるね」だけでは不合格。

**関連設計**（2026-06-30 午後以降）: [Stage1 → loop routing](../tracks/stage1-loop-routing.md)（`close_shape` · Q3a 文脈付き greeting · 許可型 POC 較正）

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

**推奨**: 新規検証は **F**（昼寝→おはよう）を先に打つと、open / Q3a close / スレッド安全の三点が一発で確認できる。

### F — 文脈付き起床挨拶（Q3a · 2026-06-30 合格済み）

| # | まー | 期待 |
|---|-----|------|
| F1 | 「ちょっと昼寝してくる」 | open loop 1 件 · `activity_frame.mode=departure` |
| F2 | 「おはよう」 | **即 close** · `ol7_completion`（または OL7 unscoped） |
| F2' | （任意）明示完了 | 「お昼寝してきた」「うん。終わった」でも close 可（F2 より冗長） |

**ログ（合格例）**:

- `GW-S2 apply: create=True kind=future_commitment …`（F1）
- `GW-S2 apply: kind=past_completion close_shape=action_only …`（F2）
- `OL7 unscoped past_completion` または `promote greeting -> past_completion`
- **エラーなし**（`gw_s2_ol_gate` の SQLite スレッド越境が出たら不合格 — 修正済み 14:50 頃）

**Stage1 の考え方**: 「おはよう」は字面では greeting だが、`open_departure_loops` が 1 件のとき **完了合図として間違いではない**（POC 許可型）→ `past_completion` + `action_only`。

departure **なし**の朝の「おはよう」だけ → 下記 **D1**（close しない）。

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
| D1 | 「おはよう」（**departure open なし** · 例: 朝イチ） | close しない · 新 loop も増やさない（`greeting`） |
| D1' | 「おはよう」（**departure が 2 件以上** open） | 即 close **しない** · OL7 または pending で選ぶ（F2 とは別） |
| D2 | 「ごちそうさま」（食事系 loop 無し） | close しない |

> **旧 D1（2026-06-30 午前）**: 「open ありならおはようで close しない」— **departure 1 件の Q3a 導入後は F2 に置き換え**。

### E — OL6（時刻あり loop があれば）

`until_phrase` 付き loop（例: 書類15時まで）が **時刻過ぎ** なら:

1. こよりが自然に「終わった？」
2. まー「終わったよ」
3. `ol6_completion`

---

## 記録テンプレ

| シナリオ | 発話 | DB closed? | close_kind | メモ |
|----------|------|------------|------------|------|
| F | 昼寝してくる→おはよう | ✅ | ol7_completion | 2026-06-30 14:50+ · Q3a · エラーなし |
| B | ジョギング→ただいま→うん。行ってきた | ✅ | ol7_completion | pending → 短答 close |
| A1 | 試合、見終わった | ❌ | — | 表層は共感のみ · 07:43 も「午前2時 WC」言及 → loop open のまま |
| B2 | 散歩→ただいま | ❌→再テスト | — | e4b `return_signal` だが `close_loop_ids=[]` → gateway `no_op`（2026-06-30 修正: resolve fallback） |
| … | | | | |

### 2026-06-30 08:56 ログ所見（`lms log stream`）

「試合、見終わった」1 発話で **e4b が 2 回**（Stage1 + Stage2）のみ。**OL7 (`task: ol7_return_signal`) は出ていない** → `PRESENCE_OL7_ENABLED=1` が worker に載っていないか、再起動前コード。

| 呼び出し | 結果 | 影響 |
|----------|------|------|
| IBF 12b | `chat` | 正常 |
| TEMP-C Stage1 | `past_completion` · object=試合 · action=見終わった | ✅ |
| TEMP-C Stage2 | `what=null` · 空 events | ❌ e4b が分解失敗（→ gateway 側で **パース後 events=0**） |

**「Stage2 が空」の意味**: LM は JSON を返しているが `events[0].what=null` など **パーサが捨てた**状態。8:56 の生出力は `{"events":[{"what":null,...}]}` だった。

**手動 LM Studio では通るのに gateway で落ちる理由**:
1. **system の conditioning 差** — 手動は system に `utterance_kind=past_completion` を明記。旧 gateway は「Stage 1 で決まった kind」だけで、較正例も future_commitment 偏重 → e4b が null 骨組み JSON を返しやすい
2. **Stage1 スロット未伝達** — 手動は発話だけ。gateway は `utterance_kind` を user に載せるが、Stage1 の object/action は Stage2 に渡していなかった（修正: `stage1_object_phrase` / `stage1_action_phrase` + kind 別 system）
3. **フォールバック** — Stage2 が空でも Stage1 から event 合成（別修正）

| OL7 | **ログなし** / `OL7 return-signal failed` | ❌ 語彙不一致（試合↔サッカーWC）を救う経路が未実行 |

**2026-06-30 09:31 確定原因（OL7 enabled なのに LM 4本目なし）**:
`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` — `try_ol7_after_ingest` が worker スレッド内で **呼び出し元の `stores`**（別スレッドの DB 接続）を触っていた。修正: worker 内で `get_stores()` を取り直す（`deps.py` はスレッドローカル）。

**OL5 が閉じられない理由（OL7 無し時）**: loop の `action_terms` は「サッカーWC…」系で、発話の「試合」と substring 不一致。加えて Stage1 JSON に `completion_verbs` が無く、旧コードは完了動詞チェックも空だった（修正済み: `action_phrase` から seed）。

**再テスト前**: `restart-presence-ui.ps1` → 同じ発話 → ログに **4 本目** `task: ol7_return_signal` が出ること。

---

**症状**: こよりは文脈を理解（2-1 負け・散歩）しているが **`open_loops.status` は open**。07:43 返答が「これから午前2時 WC を見る予定」と **未来予定として compose されている** → gateway 側で close 経路が走っていない。

**切り分け（優先順）**:

1. **再起動前コード / env 未反映** — `PRESENCE_OL7_ENABLED=1` が worker に載っていない、または OL7 実装前の `relationship-mcp` のまま → ingest で `OL7 return-signal failed` が握りつぶされる
2. **e4b が ingest 時だけ落ちる** — 手動 POC は通るが `classify_return_signal` が `None` → route=no_op（ログ: `OL7 classifier returned None`）
3. **OL5-b の term 不一致（A1）** — loop の `action_terms` が長文フレーズで「試合」だけでは substring 不一致 · OL7 が動いていれば `explicit_completion` で救えるはず
4. **pending だけ DB 更新 · compose/plan 未連携（B2）** — `pending_check` は付くが確認質問が出ない（古い orchestrator）→ gateway 注入 `[loops_due_for_check]` で補完（2026-06-30 修正）
5. **B2 根本原因（11:00 ログ）** — e4b は `return_signal` を返すが `close_loop_ids=[]`（「出発宣言だから close しない」誤判定）。`route_ol7_classification` は ids 空 → `no_op` → pending 未設定 → こよりの「リフレッシュできた？」は 12b 表層のみ · `asked_at` なし → 「できたよ！」も close 不能。**修正**: `resolve_ol7_loop_ids()`（単一候補 / ただいま+散歩 fallback）· OL7 プロンプト較正例 · `try_ol6_pending_close` が OL7 `candidate_at` のみでも confirm を受理
6. **C 誤 close（11:25 ログ）** — 「書類も作る」= TEMP-C `future_commitment` なのに OL7 が `explicit_completion` で **同ターン作成 loop を即 close**。**修正**: GW-S2 の `utterance_kind` を OL7 に渡し · **allowlist**（`past_completion` / `greeting` / `other` のみ OL7 実行）· `future_commitment` では OL7 を呼ばない（regex blocklist は使わない）
7. **C 未 close + 洗濯 pending（12:18 ログ）** — 「お皿洗ったよ」で 3 件 open のまま。(a) 12:15「これから洗濯をしてくる」で **誤 OL7 pending**（allowlist 前）→ 洗濯に `pending_check`。(b) 旧 `_awaiting_pending_confirm` が **全 OL7 をブロック**。(c) OL5 が `お皿` vs `お皿洗い` で term 不一致。**修正**: pending あっても `past_completion` は OL7 実行 · OL5 ingest/loop term クロスマッチ
8. **ActivityFrame（2026-06-30）** — open 時 `detail_json.activity_frame`（label / object / action_stem / gloss）を保存 · close 時 Stage1 slots とフレーム照合 · 1 件一致→即 close · 複数→OL7 LLM · none/低 confidence→pending または no-op
9. **Q3a + SQLite スレッド（14:46 ログ）** — `fetch_stage1_departure_hints` を `asyncio.to_thread` 内で呼ぶと `gw_s2_ol_gate failed: ProgrammingError` → **open すら走らない**。**修正**: departure 一覧は ingest スレッドで取得 · LLM のみ worker（`test_ol_gate_async_thread.py`）

**再テスト前チェック**:

```powershell
# env
Select-String PRESENCE_OL7 $env:USERPROFILE\.config\embodied-claude\presence-ui.local.env

# 依存 + 再起動（必須）
cd C:\Users\ma\src\embodied-claude
.\scripts\restart-presence-ui.ps1

# 1 発話後にログ（presence-ui コンソール）
#   OL7 ingest: route=immediate_close|pending_confirm|no_op
#   OL7 classify: signal=... reason=...
```

**手動でサッカー loop を掃除する場合**（再テスト用）:

```powershell
sqlite3 $env:USERPROFILE\.claude\sociality\social.db "
UPDATE open_loops SET status='closed', updated_at=datetime('now')
WHERE loop_id='loop_a03a04dfb7' AND status='open';"
```

---

## 失敗時の切り分け

| 症状 | 疑うところ |
|------|------------|
| 表層だけ反応 · DB open | OL7 未 enable · ingest 順 · `relationship-mcp` 古い |
| **open すら増えない** · `gw_s2_ol_gate failed` | SQLite スレッド越境（#9）· `presence-ui.log` |
| pending にならない | `PRESENCE_OL7_ENABLED` · e4b 落ち · GW-S2 off |
| 確認後も close しない | `mark_loop_check_asked` / `try_ol6_pending_close` · 「うん」が regex に合うか |
| 別 loop が閉じる | 複数 open · 分類器の `close_loop_ids` — DB の `loop_id` を照合 |
| おはようで閉じない（昼寝 open 中） | Q3a / `open_departure_loops` 注入 · promote ログ · e4b が greeting のまま |

ログ: presence-ui コンソールに `OL7 return_signal` / `OL5-b` 周辺。

---

## テスト後

- Close が通った経路を [ol5.md § OL7](../tracks/ol5.md) に ✅ メモ
- **F（昼寝→おはよう）** が通れば Close Epic は完了扱いでよい
- 問題なければ **TEMP-C5**（`この後 午前2時` → `start_at`）実装へ → [utterance-anchoring.md § TEMP-C5](../tracks/utterance-anchoring.md#temp-c5--clock--相対時刻アンカー設計--2026-06-29)

```powershell
# 回帰（自動 · 任意）
cd C:\Users\ma\src\embodied-claude\sociality-mcp\packages\social-core
uv run pytest tests/test_activity_frame.py -q

cd C:\Users\ma\src\embodied-claude\sociality-mcp\packages\relationship-mcp
uv run pytest tests/test_open_loops_reminders.py -q -k "ol5 or ol6 or ol7"

cd C:\Users\ma\src\embodied-claude\presence-ui
uv run pytest tests/test_ol7_flow.py tests/test_ol7_return_signal.py `
  tests/test_ol_gate.py tests/test_stage1_context.py `
  tests/test_prompt_permissive_framing.py `
  tests/test_ol7_async_thread.py tests/test_ol_gate_async_thread.py -q
```
