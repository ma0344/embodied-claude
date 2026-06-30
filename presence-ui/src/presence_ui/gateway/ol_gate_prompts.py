"""GW-S2 / OL-GATE — utterance classifier prompts (v4, stateless LM Studio)."""

# ruff: noqa: E501 — prompt text is intentionally long single lines

from __future__ import annotations

from typing import Sequence

from presence_ui.gateway.stage1_context import Stage1DepartureHint, append_stage1_departure_context

# Canonical Stage1 system prompt (TEMP-C + legacy OL-GATE extract share this).
STAGE1_SYSTEM = """あなたは会話発話の **open loop 入口フィルタ** です。まー（人間）の発話 1 文を、下の **判断フロー（順番固定）** で通し、JSON 1 件だけを出力してください。

## 判定の心構え（POC 較正 · 必須）

**「適切か」「自然か」で厳しく採点しない。** 辞書的・時間帯の常識で FALSE にしない。
代わりに **「完了・復帰の合図として間違いと断定できるか」** で判定する（POC の TRUE/FALSE 相当）。

- **TRUE（許可）** = その open departure のあと、まーが**実際に言いうる**短い合図 · **拒否できない**
- **FALSE（拒否）** = 就寝宣言・無関係 · **完了合図として明確に間違い**（例: もう寝る → おはよう）

## 判断フロー（上から順 · 最初に当てはまったら確定 · 後戻り禁止）

**Q1 — Googleカレンダー操作か？**（「カレンダーに」「予定をずらして」等）
→ YES: `utterance_kind=calendar_operation` · slots は null 可 · `close_shape=null` → 終了

**Q2 — 訂正・境界・話題 dismiss か？**（違う / 忘れて / 静かに / しつこい 等）
→ YES: `utterance_kind=correction` · `close_shape=null` → 終了

**Q3 — 短い挨拶か？**（おはよう / またね 等 · **ただいま・おかえり単独**は Q4 へ）
→ NO: Q4 へ
→ YES: **Q3a** へ

**Q3a — 出発タスクからの復帰・起床挨拶か？**（user に `open_departure_loops` があるとき **必ず読む**）
- 発話が **wake/return 挨拶**（おはよう / おはー / 起きた / おきた 等 · **活動名を含まない**短句）
- かつ `open_departure_loops` が **ちょうど 1 件**
- 問い: **その departure のあと、この発話を完了合図として使うのが間違いではないか？**（朝の挨拶の字面だけで FALSE にしない）
→ YES（間違いではない）: `utterance_kind=past_completion` · `close_shape=action_only` · `object_phrase=null` · `action_phrase`=発話の核（おはよう / 起きた 等）→ 終了
→ NO（間違いと断定できる / 複数 departure で特定不可）: `utterance_kind=greeting` · `close_shape=null` → 終了（OL7 が後段で選ぶ）
- `open_departure_loops` が **(none)** → `utterance_kind=greeting` · `close_shape=null` → 終了

**Q4 — 行動の完了報告か？**（タスクを終えた / 帰った / 済んだ — **完了合図として間違いではない** · POC TRUE 相当）
→ YES: `utterance_kind=past_completion` → Q4a へ
→ NO: Q5 へ

**Q4a — past_completion の slots**
- `action_phrase` **必須**（終わった / 行ってきた / してきた / 食べた / 作った 等 · 文中のまま）
- `object_phrase`: 活動名が文中にあれば抽出 · なければ null
- `close_shape`:
  - `activity_named` — object あり（例: お昼寝をしてきた / 角煮、作った）
  - `action_only` — object なし（例: 終わった / 行ってきた / してきたよ / ただいま）
- `completion_verbs`: action_phrase を含める（最大5）
→ 終了

**Q5 — これからやる予定・出発宣言か？**（これから行く / してくる / 明日作る — POC の「散歩に行ってくる」= FALSE 相当）
→ YES: `utterance_kind=future_commitment` · `close_shape=null` → 終了

**Q6 — 過去の叙述か？**（昨日ロバが / 頭が痛かった — タスク完了ではない）
→ YES: `utterance_kind=past_report` · `close_shape=null` → 終了

**Q7 — それ以外**（願望・雑談・疲れた・記憶質問 等）
→ `utterance_kind=other` · `ineligibility_reason` に短い理由 · `close_shape=null`

## 完了報告 vs 非完了（POC 較正 · 必須）

| 発話 | kind | close_shape |
|------|------|-------------|
| ご飯食べたよ | past_completion | activity_named |
| 終わった / 終わったよ | past_completion | action_only |
| 行ってきた / してきたよ | past_completion | action_only |
| ただいま / ただいまー | past_completion | action_only |
| 散歩行ってきた | past_completion | activity_named |
| お昼寝をしてきた | past_completion | activity_named |
| お昼寝 終わった | past_completion | activity_named |
| 試合、見終わった | past_completion | activity_named |
| これから散歩に行ってくる | future_commitment | null |
| 頭が痛かった | past_report | null |
| 今日は疲れた | other | null |
| おはよう | greeting | null |
| おはよう（open_departure=昼寝 1件） | past_completion | action_only |

## コロケーション較正（POC · 間違いではないか？ · Q3a/Q4 の参考）

出発宣言（open）に対し、完了合図候補が **間違いではない（TRUE）** か **間違い（FALSE）** か。

| 出発（行動予告） | 合図: ただいま | 合図: おはよう |
|------------------|----------------|----------------|
| 昼寝してくる | TRUE | TRUE |
| 公園に行ってくる | TRUE | — |
| トイレに行ってくる | TRUE | — |
| もう寝る / 寝る（就寝） | FALSE | FALSE |
| ちょっと横になる | TRUE（短い離席） | FALSE（就寝・休憩宣言ではないが起床合図とも限らない） |

- **ただいま** — 物理的離席・行ってくる系は TRUE · 就寝宣言のみ FALSE
- **おはよう** — **昼寝してくる** のあとなら TRUE（起床合図として拒否できない）· **もう寝る** は FALSE · open_departure なしの単独「おはよう」は Q3a 前に greeting

## open_departure_loops（Q3a 用 · gateway が注入）

- user メッセージ末尾の `open_departure_loops:` を読む · 推測で loop を足さない
- **(none)** なら Q3a はスキップして greeting

## slots 共通ルール

- 文中の語だけ · 推測・補完禁止
- `temporal_phrase`: 明示の「いつ」のみ
- `inferred_temporal_phrase`: future/past_completion で when なしのときのみ最小推測
- `action_terms`: object から OL5 用（future / past_completion のみ · 最大5）

## 出力 JSON（フィールド名厳守）

```json
{
  "utterance": "<入力そのまま>",
  "utterance_kind": "future_commitment | past_completion | past_report | greeting | correction | calendar_operation | other",
  "close_shape": "activity_named | action_only | null",
  "temporal_phrase": "<string or null>",
  "inferred_temporal_phrase": "<string or null>",
  "temporal_source": "explicit | inferred | null",
  "object_phrase": "<string or null>",
  "action_phrase": "<string or null>",
  "action_terms": [],
  "completion_verbs": [],
  "ineligibility_reason": "<string or null>"
}
```

- `close_shape`: **past_completion のときのみ** · それ以外は null
- past_completion では `action_phrase` を null にしない

JSON のみ。markdown フェンス不可。"""

TEMP_C_STAGE1_SYSTEM = STAGE1_SYSTEM

# Legacy non-staged extract — same decision flow (kinds unified).
OL_GATE_CLASSIFIER_STABLE = STAGE1_SYSTEM


def build_ol_gate_extract_task(
    *,
    utterance: str,
    open_departure_loops: Sequence[Stage1DepartureHint] = (),
) -> str:
    u = utterance.strip().replace("\n", " ")
    lines = [
        "[gateway_internal — not for まー]",
        "task: ol_gate_extract",
        f"utterance: {u}",
    ]
    append_stage1_departure_context(lines, open_departure_loops)
    return "\n".join(lines) + "\n"


def build_temp_c_stage1_task(
    *,
    utterance: str,
    open_departure_loops: Sequence[Stage1DepartureHint] = (),
) -> str:
    u = utterance.strip().replace("\n", " ")
    lines = [
        "[gateway_internal — not for まー]",
        "task: temp_c_stage1",
        f"utterance: {u}",
    ]
    append_stage1_departure_context(lines, open_departure_loops)
    return "\n".join(lines) + "\n"


TEMP_C_STAGE2_RULES = """**ルール**

1. 1 文に複数の予定・報告があるときは **events を複数**にする（最大 4）
2. 推測で日付を足さない — when / until / after / lag は **原文に現れる語句**のみ
3. `depends_on` — 後の event が前の event の後だと文から読めるとき、前の index を入れる
4. `certainty` — 「かかりそう」「かも」→ `estimate` · 断定 → `firm` · 不明 → null
5. `commitment_strength` — 全体のトーン。「感じだね」「かな」→ `tentative` · 断定 → `firm`

**what と action_phrase（重要 — 小モデル向け）**

- `what` = **名詞句・活動名のみ**（入浴介助 / 試合 / 豚バラ軟骨角煮）。**動詞を what に入れない**
- `action_phrase` = **動詞・動作句のみ**（作る / 見終わった / 食べる）。文中に動詞があれば **必ずここに分離**
- ❌ what=null · action_phrase=null の events[0] は **不合格**
- ❌ what=「豚バラ軟骨角煮を作る」, action_phrase=null
- ✅ what=「豚バラ軟骨角煮」, action_phrase=「作る」
- `utterance_kind=future_commitment` で **これからやる行為**がある event は、原則 **action_phrase を null にしない**
- `utterance_kind=past_completion` では **what と action_phrase を null にしない**（1 event でも両方埋める）
- **例外**: 所要時間だけのブロック（入浴介助で15時まで等）で **完了動詞が文中に無い** event は action_phrase=null 可
- user に `stage1_object_phrase` / `stage1_action_phrase` があるときは **そのまま events[0] にコピー**（再推論しない）

**較正例（future_commitment · 必須合格）**

発話: 「今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。」

期待（参考・そのままコピー不要）:
{"commitment_strength":"tentative","events":[
  {"index":0,"what":"入浴介助","when_phrase":"今日","until_phrase":"15時位まで","action_phrase":null,"certainty":"estimate","depends_on":null},
  {"index":1,"what":"豚バラ軟骨角煮","after_phrase":"帰ってきたら","lag_phrase":"すぐ","action_phrase":"作る","depends_on":0}
]}

**較正例（past_completion · 必須合格）**

発話: 「試合、見終わった」

期待:
{"commitment_strength":"firm","events":[
  {"index":0,"what":"試合","when_phrase":null,"until_phrase":null,"after_phrase":null,"lag_phrase":null,"action_phrase":"見終わった","certainty":"firm","depends_on":null}
]}

発話: 「お昼寝をしてきた」

期待:
{"commitment_strength":"firm","events":[
  {"index":0,"what":"お昼寝","when_phrase":null,"until_phrase":null,"after_phrase":null,"lag_phrase":null,"action_phrase":"してきた","certainty":"firm","depends_on":null}
]}

**フィールド**: what, when_phrase, until_phrase, after_phrase, lag_phrase, action_phrase, certainty, depends_on

JSON のみ。markdown フェンス不可。"""

_STAGE2_KIND_LABELS: dict[str, str] = {
    "future_commitment": "future_commitment（これからの予定）",
    "past_completion": "past_completion（やり終えた報告）",
    "past_report": "past_report（過去の出来事）",
}


def build_temp_c_stage2_system(*, utterance_kind: str) -> str:
    """Kind-specific Stage 2 system prompt (matches manual LM Studio conditioning)."""
    label = _STAGE2_KIND_LABELS.get(utterance_kind, utterance_kind)
    return (
        "あなたは会話発話のイベント分解器です。"
        f"utterance_kind が **{label}** である与えられた発話を、"
        "**文中の語だけ**で events[] に分解し JSON 1 件だけを出力してください。\n\n"
        f"{TEMP_C_STAGE2_RULES}"
    )


# Backward-compatible alias for tests/docs that referenced a single static prompt.
TEMP_C_STAGE2_SYSTEM = build_temp_c_stage2_system(utterance_kind="future_commitment")


def build_temp_c_stage2_task(
    *,
    utterance: str,
    utterance_kind: str,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
) -> str:
    u = utterance.strip().replace("\n", " ")
    lines = [
        "[gateway_internal — not for まー]",
        "task: temp_c_stage2",
        f"utterance_kind: {utterance_kind}",
        f"utterance: {u}",
    ]
    obj = (object_phrase or "").strip()
    act = (action_phrase or "").strip()
    if obj:
        lines.append(f"stage1_object_phrase: {obj}")
    if act:
        lines.append(f"stage1_action_phrase: {act}")
    if obj or act:
        lines.append(
            "hint: stage1 slots above — copy into events[0].what / events[0].action_phrase when kind=past_completion"
        )
    return "\n".join(lines) + "\n"


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
