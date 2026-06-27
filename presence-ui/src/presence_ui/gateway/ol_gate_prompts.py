"""GW-S2 / OL-GATE — utterance classifier prompts (v4, stateless LM Studio)."""

# ruff: noqa: E501 — prompt text is intentionally long single lines

from __future__ import annotations

OL_GATE_CLASSIFIER_STABLE = """あなたは会話発話の分類器です。まー（人間）の発話 1 文を解析し、**必ず次の順序**で考えてから JSON 1 件だけを出力してください。

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

JSON のみ返すこと。markdown フェンス不可。"""


def build_ol_gate_extract_task(*, utterance: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return f"[gateway_internal — not for まー]\ntask: ol_gate_extract\nutterance: {u}\n"
