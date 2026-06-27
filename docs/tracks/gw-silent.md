# GW-SILENT — 黙考ルート（silent internal turn）

**状態**: ✅ S1 配線済（tick PAUSE）· ✅ S2 実装済（ingest OL-GATE、既定 OFF）· 📋 Claude resume  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**第一用途**: LW-READ PAUSE（v1）、OL5 完了語セット生成  
**ループ上の位置**: BIO Heartbeat の **interpret** 層（`notice → interpret → choose → act → remember → schedule`）  
**関連**: [architecture/gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[ops/lmstudio-kv-cache.md](../ops/lmstudio-kv-cache.md)、[ol5.md](./ol5.md)

---

## なぜ GW が優先か

LW（読書）、BIO Heartbeat（`notice→interpret→choose→act→remember→schedule`）、将来の **K**（自己改修）は同じループ構造。**GW-SILENT = 共有の interpret 層**。B2 のような機械オペより根本的。

---

## やりたいこと

まーに見せないが **こより本人の文脈・人格・KV prefix** で LM に考えさせ、結果だけ gateway が parse して stores に保存する。

**別プレーンの単発 API は使わない** — prefix がコールドになり再読み込みリスクが高い。

---

## 本線経路

```
まー発話（通常ターン N）
  → ingest / compose / plan → 表向き返答
  → [背景] 同じ session_id（--resume）で internal turn N+1
       message: [gateway_internal] + 構造化タスク
       appendSystemPrompt: build_gateway_stable_append()（毎ターン同一）
       forward=False — UI に流さない
  → gateway が JSON parse → stores / detail_json
```

| 経路 | KV 再利用 | まーに見える |
|------|-----------|--------------|
| Native chat | ◎ | はい |
| `write_private_reflection`（現状） | — | いいえ（テンプレ） |
| **GW-SILENT** | ◎（同一セッション） | いいえ |

---

## 実装候補

| ID | 内容 | 状態 |
|----|------|------|
| GW-S1 | `run_silent_internal_turn(session_id, task, schema)` | ✅ 2026-06-25（tick: LM Studio + stable append） |
| GW-S1-prompt | LW-READ PAUSE 用 `build_gw_s1_pause_task` | ✅ 2026-06-26 |
| GW-S2 | ingest 後 5W1H 抽出 + loop 作成判定 + OL5 語セット seed | ✅ 2026-06-25（`PRESENCE_GW_S2_ENABLED=1`） |
| GW-S3 | 共通 JSON parse / validate | 📋 |

コード: `presence-ui/.../gw_silent.py`、`ol_gate.py`、`ol_gate_prompts.py`、`reading_prompts.py`（`PAUSE_RESPONSE_SCHEMA`, `FELT_HINTS`）

---

## 運用メモ

- 表返答の **後** に background 実行
- LM Studio **Concurrent Predictions = 1** を維持
- internal turn は **MCP スリム**（tool 定義を毎回載せない）
- 参照: `social_chat.py`（`stream_silent_response`）、`prompt_injection.py`

---

## 他用途（未着手）

| 用途 | 出力先 | 状態 |
|------|--------|------|
| **OL-GATE** 5W1H 抽出 → loop 作るか | `open_loops` or 作らない | ✅ GW-S2 |
| OL5 完了語セット | `open_loops.detail_json` | ✅ OL5-a（ヒューリスティック seed）· 📋 LLM 生成 |
| OL2 曖昧日付補完 | `needs_date_confirmation` | 📋 |
| MEM 多視点 encode | gist / 視点ラベル | 📋 |
| 夜間 digest 前処理 | トピック正規化 | 📋 |

### GW-S2 — OL-GATE（When / What / How 抽出）

ingest 直後の internal turn。**不足を推測で補わない** — 文中に現れる **いつ・何を・どうする** の語だけ抜き出す。フォローアップとして成立しなければ `is_follow_up_task: false` + `ineligibility_reason`。

**手動スモーク v2（2026-06-26, `google/gemma-4-12b-qat`）**

| 例文 | temporal | object | action | `is_follow_up_task` | メモ |
|------|----------|--------|--------|---------------------|------|
| いつも一緒にいたかった | いつも | 一緒に | いたかった | **false** | 願望・「いつも」はタスクの When ではない |
| 明日、角煮を作る | 明日 | 角煮を | 作る | **true** | loop 候補 |
| 昨日、ロバがコケた | 昨日 | ロバが | コケた | **true** | 抽出は可。**過去** → open loop ではなく remember/STM 側 |
| また明日！ | 明日 | — | — | **false** | phatic・挨拶 |

**責務分担**

| 層 | フィールド | 誰が決める |
|----|-----------|-----------|
| LLM（黙考） | `utterance`, `temporal_phrase`, `object_phrase`, `action_phrase`, `is_follow_up_task`, `ineligibility_reason` | Gemma |
| Gateway（コード） | `resolved_date`, `is_future_commitment`, `create_open_loop`, `loop_topic`, `action_terms`, `completion_verbs` | `relationship_mcp` + `date_resolution` |

```
create_open_loop = is_follow_up_task && is_future_commitment
```

`is_follow_up_task=true` でも **昨日** は `is_future_commitment=false` → loop なし。挨拶は object/action 欠落で `is_follow_up_task=false`。

**LLM 出力 schema（`OL_GATE_EXTRACT_SCHEMA`）**

```json
{
  "utterance": "明日、角煮を作る",
  "temporal_phrase": "明日",
  "object_phrase": "角煮を",
  "action_phrase": "作る",
  "is_follow_up_task": true,
  "ineligibility_reason": null
}
```

```json
{
  "utterance": "また明日！",
  "temporal_phrase": "明日",
  "object_phrase": null,
  "action_phrase": null,
  "is_follow_up_task": false,
  "ineligibility_reason": "挨拶であり、対象と動作を表す語が含まれない"
}
```

**Gateway がマージしたあと（DB 書き込み用）**

```json
{
  "utterance": "明日、角煮を作る",
  "temporal_phrase": "明日",
  "object_phrase": "角煮を",
  "action_phrase": "作る",
  "is_follow_up_task": true,
  "ineligibility_reason": null,
  "resolved_date": "2026-06-27",
  "is_future_commitment": true,
  "create_open_loop": true,
  "loop_topic": "明日、角煮を作る",
  "action_terms": ["角煮"],
  "completion_verbs": ["作った", "できた"]
}
```

プロンプト要件: **推測禁止**・JSON のみ・不適格なら `ineligibility_reason` に理由（空なら `null`）。Who/Where は聞かない。

`action_terms` / `completion_verbs` は `create_open_loop=true` のとき同ターンで載せ OL5 close に使う。

詳細 → [open-loops-reminders.md § OL-GATE](../architecture/open-loops-reminders.md#ol-gate--loop-作成条件設計メモ合意-2026-06-26)

### 検討 — `utterance_kind` 三分類（**v3 スモークで推奨度↑**）

**手動スモーク v3（2026-06-26, 8 例）** — プロンプトは v2 同型（3 スロット + canGet 相当）。Gemma 出力は旧フィールド名のまま；下表は **意図する schema 名**で再掲。

| # | 例文 | temporal | object | action | Gemma canGet | **望ましい `utterance_kind`** | gateway |
|---|------|----------|--------|--------|--------------|-------------------------------|---------|
| 1 | いつも一緒にいたかった | いつも | 一緒に | いたかった | **揺れた**（v2:false → v3:**true**） | `other` | 何もしない |
| 2 | 明日、角煮を作る | 明日 | 角煮を | 作る | true | `future_commitment` | `create_open_loop` |
| 3 | 昨日、ロバがコケた | 昨日 | ロバが | コケた | true | `past_report` | remember/STM（loop しない） |
| 4 | また明日！ | 明日 | — | — | false | `other` | 何もしない |
| 5 | 角煮、作った | — | 角煮 | 作った | false※ | `past_completion` | **OL5 close** 候補 |
| 6 | 散歩行ってきた | — | 散歩 | 行ってきた | false※ | `past_completion` | **OL5 close** 候補 |
| 7 | 昼から出かける | 昼から | — | 出かける | false | `future_commitment`? | when+how のみ — object 暗黙 |
| 8 | ごはん食べる | — | ごはん | 食べる | false | `future_commitment`? | when なし — 日付未アンカー |

※ Gemma は「いつが無いから canGet=false」だが、**完了報告では when は不要**。3 スロット一律ルールの限界。

**教訓**

1. **例文1の揺れ** — スロット抽出は機械的に埋まる（いつも/一緒に/いたかった）ので `is_follow_up_task` だけでは不安定。**先に `utterance_kind` を聞く**か、プロンプトで「いつも」は scheduling の temporal にしないと明示。
2. **例文5–6** — OL5 用の `past_completion` を **canGet と切り離す**。`object_phrase` + 完了形 `action_phrase` あれば close 照合へ（open loop 作成とは別ルート）。
3. **例文7–8** — 未来予定でも when または what が欠けることがある。`future_commitment` + gateway で `resolved_date` 任意 / `needs_date_confirmation`。

**改訂スキーマ（LLM）**

```json
{
  "utterance": "角煮、作った",
  "utterance_kind": "past_completion",
  "temporal_phrase": null,
  "object_phrase": "角煮",
  "action_phrase": "作った",
  "ineligibility_reason": null
}
```

```json
{
  "utterance": "いつも一緒にいたかった",
  "utterance_kind": "other",
  "temporal_phrase": null,
  "object_phrase": null,
  "action_phrase": null,
  "ineligibility_reason": "願望・回想であり予定でも完了報告でもない"
}
```

**Gateway ルーティング（案）**

```
utterance_kind == future_commitment
  && object_phrase && action_phrase
  && is_future_commitment(temporal_phrase)
  → create_open_loop

utterance_kind == past_completion
  && object_phrase && action_phrase
  → match open_loops.action_terms + completion overlap → close

else → 何もしない（remember / phatic は別経路）
```

`is_follow_up_task` は **`future_commitment` 専用**に縮小するか廃止。英訳ステップは依然 **任意**（`utterance_kind` を日本語プロンプトで直接返すのが先）。

### プロンプト草案 v4 — `utterance_kind` 先行（LM Studio 手動用）

実装時は `build_ol_gate_extract_task()` として `reading_prompts.py` 近辺に置く想定。JSON **のみ**返すこと。

````
あなたは会話発話の分類器です。まー（人間）の発話 1 文を解析し、**必ず次の順序**で考えてから JSON 1 件だけを出力してください。

## 手順（この順を守る）

1. **utterance_kind を先に 1 つだけ決める**（下表）
2. **object_phrase / action_phrase** — 文中に現れる語だけ抜き出す（推測・補完禁止）
3. **temporal_phrase** — 文中の「いつ」に相当する語だけ（推測禁止）
4. **inferred_temporal_phrase** — 手順3が null のときだけ、手順1が許す場合に限り推測（下表）

## utterance_kind（4 値）

| 値 | 意味 | 例 |
|----|------|-----|
| `future_commitment` | これからやる予定・してほしい約定 | 「明日、角煮を作る」「ごはん食べる」 |
| `past_completion` | やり終えた・済んだ報告（既存の予定の消化） | 「角煮、作った」「散歩行ってきた」 |
| `past_report` | 過去の出来事の叙述（予定の完了報告ではない） | 「昨日、ロバがコケた」 |
| `other` | 挨拶・願望・回想・雑談・記憶質問など | 「また明日！」「いつも一緒にいたかった」 |

**分類の注意**
- 「また明日」「じゃあね」→ `other`（挨拶）。when があっても予定ではない
- 「いつも」「ずっと」「昔」だけの時間表現 → 予定の when にしない → 多くは `other`
- 「作った」「行ってきた」「済んだ」「終わった」で **タスク完了** → `past_completion`
- 「昨日〜た」で単なるエピソード → `past_report`

## スロット抽出ルール

- `object_phrase`: 動作の対象・話題の名詞句（文中のまま）。無ければ null
- `action_phrase`: 動詞・動作句（文中のまま）。無ければ null
- `temporal_phrase`: 文中の時間表現（明日、昨日、昼から、9時…）。**無ければ null**
- `inferred_temporal_phrase`: **次のときだけ**設定可。それ以外は null
  - `future_commitment` かつ `temporal_phrase` が null → 「今日」「今度」など最小限の推測可
  - `past_completion` かつ `temporal_phrase` が null → 「いま」「今日」など最小限の推測可
  - `other` / `past_report` → **常に null**（推測しない）

## 出力 JSON（フィールド名は厳守）

```json
{
  "utterance": "<入力文そのまま>",
  "utterance_kind": "future_commitment | past_completion | past_report | other",
  "temporal_phrase": "<string or null>",
  "inferred_temporal_phrase": "<string or null>",
  "temporal_source": "explicit | inferred | null",
  "object_phrase": "<string or null>",
  "action_phrase": "<string or null>",
  "action_terms": ["<OL5用・objectから>", "..."],
  "completion_verbs": ["<past_completion時のみ・完了表現>", "..."],
  "ineligibility_reason": "<string or null>"
}
```

- `temporal_source`: `temporal_phrase` があれば `explicit`；`inferred_temporal_phrase` のみなら `inferred`；どちらもなければ `null`
- `action_terms` / `completion_verbs`: `future_commitment` または `past_completion` のときだけ埋める（最大各5語）。`other` は `[]`
- `ineligibility_reason`: `other` で分類理由を短く。それ以外は null

## 較正例（期待）

| 発話 | utterance_kind |
|------|----------------|
| いつも一緒にいたかった | other |
| 明日、角煮を作る | future_commitment |
| 昨日、ロバがコケた | past_report |
| また明日！ | other |
| 角煮、作った | past_completion |
| 散歩行ってきた | past_completion |
| 昼から出かける | future_commitment |
| ごはん食べる | future_commitment（inferred: 今日 可） |

---

入力:
{{utterance}}
````

**ポイント**: 「先に kind」とはプロンプト上 **手順1を明示**し、較正例で挨拶・願望を `other` に固定すること。Chain-of-thought を JSON 外に書かせるとパースが面倒なので、**思考はさせず表と較正例で誘導**（GW 本番も `forward=false` でまーに見せない）。

### 手動スモーク v4 結果（2026-06-26）

**構成**: LM Studio **system** = v4 全文固定 / **user** = 発話 1 文のみ。レイテンシ **≤0.7s**。

| # | 発話 | kind（期待） | kind（結果） | メモ |
|---|------|-------------|-------------|------|
| 1 | いつも一緒にいたかった | other | **other** ✓ | `action_phrase` が残る → **gateway は kind=other ならスロット無視** |
| 2 | 明日、角煮を作る | future_commitment | ✓ | `action_terms` は名詞「角煮」寄せが望ましい（後処理可） |
| 3 | 昨日、ロバがコケた | past_report | ✓ | |
| 4 | また明日！ | other | ✓ | 完全 |
| 5 | 角煮、作った | past_completion | ✓ | inferred いま ✓ |
| 6 | 散歩行ってきた | past_completion | ✓ | object null — OL5 は `completion_verbs` 優先 |
| 7 | 昼から出かける | future_commitment | ✓ | object null — when+how のみで可 |
| 8 | ごはん食べる | future_commitment | ✓ | inferred 今日 ✓ |

**v4 合格**: `utterance_kind` **8/8**。次の課題は **こより本線セッションに載せないこと**。

層の全体像（表層 / 前頭葉 / 内省 / MEM-8 接続）→ [architecture/cognitive-layers.md](../architecture/cognitive-layers.md)

### KV を殺さない載せ方（OL-GATE vs LW-READ）

| 用途 | セッション | system / stable | user（毎回変わる） | 理由 |
|------|-----------|-----------------|-------------------|------|
| **OL-GATE**（ingest） | **別枠・履歴なし** | `OL_GATE_CLASSIFIER_STABLE`（v4 全文） | 下記 3 行のみ | 分類器。SOUL 不要。本線 JSONL/KV を汚さない |
| **LW-READ PAUSE**（GW-S1） | **本線 `--resume` 後** | `build_gateway_stable_append()`（既存） | `build_gw_s1_pause_task(...)` | こよりの内省。SOUL 要る |

**OL-GATE の毎回 user メッセージ（固定テンプレ・可変は utterance だけ）**

```
[gateway_internal — not for まー]
task: ol_gate_extract
utterance: 明日、角煮を作る
```

実装イメージ:

```python
# ol_gate_prompts.py（案）
OL_GATE_CLASSIFIER_STABLE = "..."  # v4 全文。定数でコミット可

def build_ol_gate_extract_task(*, utterance: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return f"[gateway_internal — not for まー]\ntask: ol_gate_extract\nutterance: {u}\n"
```

**API 呼び出し（ingest 後・background）**

```
messages = [
  {"role": "system", "content": OL_GATE_CLASSIFIER_STABLE},
  {"role": "user", "content": build_ol_gate_extract_task(utterance=...)},
]
# session_id なし / 履歴なし — 単発 completion（まーの手動試験と同型）
```

- **本線 native chat の `appendSystemPrompt` に v4 を足さない**（毎ターン肥大 + KV 不安定）
- ingest のみでセッション無し → **キュー** `ol_gate_pending.jsonl` 等で次 chat まで遅延可
- 表返答の **後** `create_task` — Concurrent Predictions = 1

**gateway 後処理（LLM を信じすぎない）**

- `utterance_kind == other` → スロット無視、loop 作成/close しない
- `future_commitment` → `action_terms` は `object_phrase` 優先（動詞混入は strip）
- `past_completion` → `completion_verbs` で OL5 close

---

## v1 運用（2026-06-25 合意）

- **GW-S1 配線済** — tick PAUSE で LM Studio + `build_gateway_stable_append()`。LLM 失敗時 v0 テンプレ。
- **GW-S2 配線済** — Native chat ingest 後に stateless 分類器（v4 prompt）。`PRESENCE_GW_S2_ENABLED=1` で有効（**既定 OFF**）。ON 時は v0 `FUTURE_MARKERS` loop 作成を抑止。
- **デバッグ** — `list_open_loops` が `detail`（when/what/how、`completion_verbs`）を返す。
- **次**: Claude `--resume` 経路（チャット直後 KV 再利用）、OL5 close の ma-home 運用確認。
- **環境**: `PRESENCE_GW_S1_ENABLED=1`（既定）、`PRESENCE_GW_S1_TIMEOUT=90`、`PRESENCE_GW_S2_ENABLED=1`（本番 ON 時）。
