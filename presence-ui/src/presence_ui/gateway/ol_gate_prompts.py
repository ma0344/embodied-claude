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


# --- TEMP-C staged classification (Stage 1 + Stage 2) — see prottypemarkdown.md ---

TEMP_C_STAGE1_SYSTEM = """あなたは会話発話の分類器です。まー（人間）の発話 1 文を解析し、**必ず次の順序**で考えてから JSON 1 件だけを出力してください。

**手順**

1. `utterance_kind` を先に 1 つ決める
2. `object_phrase` / `action_phrase` — 文中の語だけ（推測禁止）
3. `temporal_phrase` — 文中の「いつ」だけ（推測禁止）
4. `inferred_temporal_phrase` — 手順3が null かつ kind が許すときだけ

**utterance_kind**

| 値 | 意味 | 例 |
|----|------|-----|
| `future_commitment` | これからの予定 | 明日角煮を作る / ごはん食べる |
| `past_completion` | やり終えた報告 | 角煮、作った / 散歩行ってきた |
| `past_report` | 過去の出来事 | 昨日、ロバがコケた |
| `greeting` | 挨拶 | また明日！/ おはよう / またね |
| `correction` | 訂正・境界・忘れて・違う | 違うみたい / 夜は静かに / 〜の話は忘れていい |
| `other` | 願望・雑談 | いつも一緒にいたかった |

**注意**: 「また明日」→ `greeting`。「いつも」は予定の when にしない → `other`。完了形（作った・行ってきた）→ `past_completion`。

**inferred_temporal_phrase**（いつだけ推測可）

* `future_commitment` かつ when なし → 「今日」など可
* `past_completion` かつ when なし → 「いま」「今日」など可
* `other` / `past_report` / `greeting` → **常に null**

JSON のみ。markdown フェンス不可。"""


TEMP_C_STAGE2_SYSTEM = """あなたは会話発話のイベント分解器です。Stage 1 で utterance_kind が決まった発話を、**文中の語だけ**で events[] に分解し JSON 1 件だけを出力してください。

**ルール**

1. 1 文に複数の予定・報告があるときは **events を複数**にする（最大 4）
2. 推測で日付を足さない — when / until / after / lag は **原文に現れる語句**のみ
3. `depends_on` — 後の event が前の event の後だと文から読めるとき、前の index を入れる
4. `certainty` — 「かかりそう」「かも」→ `estimate` · 断定 → `firm` · 不明 → null
5. `commitment_strength` — 全体のトーン。「感じだね」「かな」→ `tentative` · 断定 → `firm`

**what と action_phrase（重要 — 小モデル向け）**

- `what` = **名詞句・活動名のみ**（入浴介助 / 豚バラ軟骨角煮 / 部屋の掃除）。**動詞を what に入れない**
- `action_phrase` = **動詞・動作句のみ**（作る / やって / 食べる / 作るよ）。文中に動詞があれば **必ずここに分離**
- ❌ what=「豚バラ軟骨角煮を作る」, action_phrase=null
- ✅ what=「豚バラ軟骨角煮」, action_phrase=「作る」
- `utterance_kind=future_commitment` で **これからやる行為**がある event は、原則 **action_phrase を null にしない**
- **例外**: 所要時間だけのブロック（入浴介助で15時まで等）で **完了動詞が文中に無い** event は action_phrase=null 可
- 「作る感じだね」「やる感じ」→ action_phrase=「作る」「やる」（「感じだね」は commitment_strength 側）

**較正例（future_commitment · 必須合格）**

発話: 「今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。」

期待（参考・そのままコピー不要）:
{"commitment_strength":"tentative","events":[
  {"index":0,"what":"入浴介助","when_phrase":"今日","until_phrase":"15時位まで","action_phrase":null,"certainty":"estimate","depends_on":null},
  {"index":1,"what":"豚バラ軟骨角煮","after_phrase":"帰ってきたら","lag_phrase":"すぐ","action_phrase":"作る","depends_on":0}
]}

**フィールド**: what, when_phrase, until_phrase, after_phrase, lag_phrase, action_phrase, certainty, depends_on

JSON のみ。markdown フェンス不可。"""


def build_temp_c_stage1_task(*, utterance: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return f"[gateway_internal — not for まー]\ntask: temp_c_stage1\nutterance: {u}\n"


def build_temp_c_stage2_task(*, utterance: str, utterance_kind: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return (
        f"[gateway_internal — not for まー]\n"
        f"task: temp_c_stage2\n"
        f"utterance_kind: {utterance_kind}\n"
        f"utterance: {u}\n"
    )


# --- SHIFT-R2 correction routing (Stage 2 after Stage 1 ``correction``) ---

SHIFT_R2_CORRECTION_STAGE2_SYSTEM = """あなたは会話発話の訂正・理解更新分類器です。Stage 1 で utterance_kind=correction と判定された発話を解析し JSON 1 件だけを出力してください。

**correction_target（1 つだけ）**

| 値 | 意味 | 例 |
|----|------|-----|
| `world_fact` | 世界・事実の訂正（HP・天気・場所） | 違うみたい。松本市のHPに無いかな |
| `schedule` | 予定・スケジュールの訂正 | 違う、明日じゃなくて明後日 |
| `dismiss_topic` | 話題を忘れて・もういい | 松本市HPの話は忘れていい |
| `boundary` | 静かに・見ないで・プライバシー | 夜は静かにして |
| `relationship` | 距離感・関係 | しつこい、距離置いて |
| `rule` | 方針・ルール・ポリシー | ルールは睡眠優先で |
| `agent_behavior` | エージェントの振る舞い訂正 | そう返すんじゃなくて |
| `self_model` | 自己理解の更新 | うちはそういう存在じゃない |

**フィールド**

- `canonical_topic`: 短い英語または日本語ラベル（生発話 80 字切り捨て禁止）。例: `quiet hours and presence`
- `old_interpretation`: エージェントが以前持っていた解釈（推定可・短く）
- `new_interpretation`: まーの訂正後の解釈（文中の語をベースに）
- `persists_across_turns`: 以降のターンにも効くなら true（world_fact / dismiss は false）
- `dismiss_topic_hint`: dismiss_topic のとき loop 照合用の短いキー（null 可）
- `confidence`: 0.0–1.0

JSON のみ。markdown フェンス不可。"""


def build_shift_r2_correction_stage2_task(*, utterance: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return f"[gateway_internal — not for まー]\ntask: shift_r2_correction_stage2\nutterance: {u}\n"
