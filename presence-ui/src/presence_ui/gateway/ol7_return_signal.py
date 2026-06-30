"""OL7 — return-signal close classifier (日本語検定型 · e4b JSON).

Product goal: a **path to close open loops** — not necessarily in one utterance.
Gateway may immediate-close, set pending_check for confirmation (OL6-shaped), or no-op.
``confidence`` and ``ol7_min_confidence()`` are hints for immediate vs pending routing in POC;
they are not a permanent "never close" gate.
"""

# ruff: noqa: E501 — prompt text is intentionally long single lines

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, replace

from social_core.activity_frame import ActivityFrame, activity_gloss, is_action_only_close

from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object

logger = logging.getLogger(__name__)

VALID_SIGNALS = frozenset({"none", "explicit_completion", "return_signal"})

_KNOWN_RETURN_UTTERANCE_RE = re.compile(
    r"^(?:ただいま|ただいまー|おかえり|おかえりー|帰った|帰ってきた|戻った)(?:[!.！?？～〜*\s]*)$",
    re.I,
)
# Legacy OL7 fallback when Stage1 unavailable — prefer past_completion + close_shape=action_only.
_DEPARTURE_LOOP_RE = re.compile(r"散歩|行って(?:き|く)る|出かけ|行く")

# TEMP-C Stage1 kinds where OL7 may run (allowlist — fixed set, no verb regex).
OL7_ELIGIBLE_KINDS = frozenset({"past_completion", "greeting", "other"})

OL7_SYSTEM = """あなたは会話発話の **open loop 完了用法選択** 分類器です。
まー（人間）の短い発話が、**列挙された open loop（進行中タスク）のどれを完了した合図か**を判定し JSON 1 件だけを出力します。

## 判定の心構え（POC 較正 · 必須）

**「適切か」「自然か」で厳しく採点しない。** 辞書・時間帯（おはよう＝朝）だけで FALSE にしない。
**「その loop の完了合図として間違いと断定できるか」** で選ぶ（POC TRUE = close 許可）。

- **許可** = まーが departure のあとに**実際に言いうる**合図 · 拒否できない
- **拒否** = 就寝宣言 loop に「ただいま」等 · リスト外 · 複数同程度で特定不可

## 前提（GW-S2 連携）
user に `utterance_kind` があるとき — **それは TEMP-C Stage1 の確定判定**（あなたが上書きしない）。
- このタスクは **完了合図の loop 選択のみ** · 予定宣言の分類は Stage1 の仕事
- `past_completion` → 明示完了（昼寝終わった 等）を loop に対応付ける
- `greeting` / `other` → 短い合図（ただいま / おはよう 等）が departure と **間違いではない** とき return_signal 候補

## 比喩（日本語検定 · 許可型）
「欠陥」と同様、発話はリストの選択肢と**コロケーション（組み合わせとして拒否できないか）**でペアになるかで判定する。
- **slots**（object / action）と loop の **label / gloss** が同じ行為を指すなら close 可（例: object=お皿 + action=洗った ≒ label=お皿洗い）
- **間違いではない**組み合わせが **1 つ** に絞れるならそれを選ぶ
- **どれとも間違いと断定できる** または **複数同程度** なら close しない（正解なし → 会話側で確認）
- **リストにない行動**を推測・捏造しない

## 重要 — 出発 loop と帰宅・起床合図
- topic / departure が **「これから 散歩 行ってくる」等の出発宣言**でも、**進行中タスク**として open なら close 候補になりうる
- **「ただいま」「おかえり」** = 行ってくる系 departure への **return_signal**（帰宅・戻り · 間違いではない）
- **「おはよう」** = **昼寝してくる** 等の departure のあとなら **起床・復帰合図として間違いではない**（朝の字面だけで none にしない）
- topic 文字列と発話が完全一致しなくてよい（散歩に行く → ただいま、は許可）

## ルール
1. **選択肢は番号付き open_loops のみ**。リスト外のタスクを close しない
2. **原則 1 発話で 1 loop まで**。複数 close は同一発話に複数対象が明示された場合のみ
3. `signal`:
   - `explicit_completion`: 対象+完了語が同一発話に明確（例: 昼寝終わった、散歩行ってきた）
   - `return_signal`: 短い合図のみだが departure と **間違いではない**（例: ただいま、おかえり · おはよう+昼寝departure）
   - `none`: **間違いと断定できる**（例: 就寝宣言 loop にただいま · open loop なしの雑談 · ごちそうさま）
4. `confidence` 0.0–1.0: 許可の確信度（最適さではない）
5. `completion_summary`: 完了報告の要約（表示用）。close しないときは null

## 較正例（return_signal · ただいま · 必須合格）

発話: ただいま
open_loops: 1. loop_id=loop_x | topic=これから 散歩 行ってくる | activity=散歩 | departure=散歩

期待:
{"signal":"return_signal","choice_index":1,"close_loop_ids":["loop_x"],"confidence":0.9,"reason":"散歩の出発に対する帰宅合図·間違いではない"}

## 較正例（return_signal · おはよう + 昼寝 departure · 必須合格）

発話: おはよう
utterance_kind: past_completion
close_shape: action_only
open_loops: 1. loop_id=loop_nap | label=昼寝 | gloss=昼寝 | topic=昼寝してくる

期待:
{"signal":"return_signal","choice_index":1,"close_loop_ids":["loop_nap"],"confidence":0.88,"reason":"昼寝してくるのあとの起床合図·間違いではない"}

## 較正例（none · 就寝 · 必須合格）

発話: ただいま
open_loops: 1. loop_id=loop_sleep | topic=もう寝る | label=就寝

期待:
{"signal":"none","choice_index":null,"close_loop_ids":[],"confidence":0.85,"reason":"就寝宣言に帰宅合図は間違い"}

## 較正例（explicit_completion · past_completion）

発話: 昼寝終わった
utterance_kind: past_completion
open_loops: 1. loop_id=loop_nap | topic=お昼寝 する | activity=お昼寝
           2. loop_id=loop_docs | topic=書類 作る | activity=書類

期待:
{"signal":"explicit_completion","choice_index":1,"close_loop_ids":["loop_nap"],"confidence":0.92,"reason":"昼寝+終わった"}

## 較正例（explicit_completion · slots · 必須合格）

発話: お皿洗ったよ
utterance_kind: past_completion
slots: object=お皿 | action=洗った
open_loops:
  1. loop_id=loop_dish | label=お皿洗い | gloss=お皿を洗う行為 | departure=してくる
  2. loop_id=loop_laundry | label=洗濯 | gloss=洗濯

期待:
{"signal":"explicit_completion","choice_index":1,"close_loop_ids":["loop_dish"],"confidence":0.92,"reason":"お皿+洗ったはお皿洗いと同じ行為"}

## 較正例（unscoped past_completion · 必須合格）

発話: 終わったよ
utterance_kind: past_completion
slots: object=null | action=終わった
open_loops:
  1. loop_id=loop_nap | label=昼寝 | gloss=昼寝 | departure=してくる
  2. loop_id=loop_docs | label=書類 | gloss=書類を作る行為

期待:
{"signal":"explicit_completion","choice_index":1,"close_loop_ids":["loop_nap"],"confidence":0.9,"reason":"objectなし完了は唯一のdeparture loop(昼寝)に対応"}

## 出力 JSON
{
  "utterance": "<入力そのまま>",
  "signal": "none | explicit_completion | return_signal",
  "choice_index": <1-based int or null>,
  "close_loop_ids": ["<loop_id>"],
  "completion_summary": "<string or null>",
  "confidence": <float>,
  "reason": "<短い判定理由>"
}

- `choice_index`: 選んだ open_loops の番号（1始まり）。close しないとき null
- `close_loop_ids`: 空配列可。id は入力の loop_id をそのまま

JSON のみ。markdown フェンス不可。"""


@dataclass(frozen=True, slots=True)
class OpenLoopCandidate:
    loop_id: str
    topic: str
    departure_utterance: str
    activity_label: str = ""
    activity_frame: ActivityFrame | None = None
    frame_gloss: str = ""


@dataclass(frozen=True, slots=True)
class Ol7Classification:
    utterance: str
    signal: str
    close_loop_ids: tuple[str, ...]
    completion_summary: str | None
    confidence: float
    reason: str
    choice_index: int | None = None
    raw: str | None = None


def ol7_enabled() -> bool:
    from presence_ui.repo_env import load_repo_env

    load_repo_env()
    flag = os.environ.get("PRESENCE_OL7_ENABLED", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def ol7_min_confidence() -> float:
    try:
        return float(os.environ.get("PRESENCE_OL7_MIN_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _ol7_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_OL7_MAX_TOKENS", "320"))


def is_known_return_utterance(utterance: str) -> bool:
    return bool(_KNOWN_RETURN_UTTERANCE_RE.match((utterance or "").strip()))


def is_departure_loop_candidate(candidate: OpenLoopCandidate) -> bool:
    blob = f"{candidate.topic} {candidate.departure_utterance} {candidate.activity_label}"
    return bool(_DEPARTURE_LOOP_RE.search(blob))


def should_run_ol7_classifier(
    *,
    utterance_kind: str | None,
    gw_s2_active: bool,
) -> bool:
    """OL7 runs only when TEMP-C Stage1 says the utterance may signal loop closure."""
    if gw_s2_active:
        if utterance_kind is None:
            return False
        return utterance_kind in OL7_ELIGIBLE_KINDS
    return True


def activity_label_for_loop(*, topic: str, departure: str, detail: dict | None = None) -> str:
    """Short activity name for OL7 collocation (散歩, 試合, …)."""
    if isinstance(detail, dict):
        event = detail.get("event")
        if isinstance(event, dict):
            what = str(event.get("what") or "").strip()
            if what:
                return what
        for raw in detail.get("action_terms") or []:
            term = str(raw).strip()
            if term:
                return term.rstrip("に行く").rstrip("へ行く")
    for blob in (departure, topic):
        for token in ("散歩", "試合", "昼寝", "書類", "買い物"):
            if token in blob:
                return token
    return departure.strip()[:40] or topic.strip()[:40]


def resolve_ol7_loop_ids(
    classification: Ol7Classification,
    *,
    utterance: str,
    open_loops: list[OpenLoopCandidate],
    utterance_kind: str | None = None,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
    close_shape: str | None = None,
) -> Ol7Classification:
    """Fill close_loop_ids when the model names signal but omits ids (common on ただいま)."""
    if classification.close_loop_ids:
        return classification
    if not open_loops:
        return classification

    departure_loops = [
        cand
        for cand in open_loops
        if cand.activity_frame is not None and cand.activity_frame.mode == "departure"
    ]
    if (
        is_action_only_close(
            close_shape=close_shape,
            utterance_kind=utterance_kind,
            object_phrase=object_phrase,
            action_phrase=action_phrase,
        )
        and len(departure_loops) == 1
    ):
        cand = departure_loops[0]
        idx = open_loops.index(cand) + 1
        logger.info(
            "OL7: unscoped past_completion + single departure fallback %s",
            cand.loop_id,
        )
        return replace(
            classification,
            signal="explicit_completion",
            close_loop_ids=(cand.loop_id,),
            choice_index=idx,
            confidence=max(classification.confidence, 0.88),
            reason=f"gateway_fallback(unscoped_departure): {classification.reason}".strip(),
        )

    if classification.signal == "return_signal" and len(open_loops) == 1:
        loop_id = open_loops[0].loop_id
        logger.info("OL7: return_signal without ids — single-candidate fallback %s", loop_id)
        return replace(
            classification,
            close_loop_ids=(loop_id,),
            choice_index=1,
            reason=f"gateway_fallback(single_return): {classification.reason}".strip(),
        )

    if len(open_loops) == 1 and is_known_return_utterance(utterance):
        cand = open_loops[0]
        if is_departure_loop_candidate(cand):
            logger.info(
                "OL7: known return phrase + departure loop fallback %s",
                cand.loop_id,
            )
            return replace(
                classification,
                signal="return_signal",
                close_loop_ids=(cand.loop_id,),
                choice_index=1,
                confidence=max(classification.confidence, 0.85),
                reason=f"gateway_fallback(ただいま+散歩): {classification.reason}".strip(),
            )

    return classification


def build_ol7_task(
    *,
    utterance: str,
    open_loops: list[OpenLoopCandidate],
    utterance_kind: str | None = None,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
    close_shape: str | None = None,
) -> str:
    u = utterance.strip().replace("\n", " ")
    lines = [
        "[gateway_internal — not for まー]",
        "task: ol7_return_signal",
        f"utterance: {u}",
    ]
    if utterance_kind:
        lines.append(f"utterance_kind: {utterance_kind}")
    if close_shape:
        lines.append(f"close_shape: {close_shape}")
    if object_phrase or action_phrase:
        obj = (object_phrase or "null").strip().replace("\n", " ")
        act = (action_phrase or "null").strip().replace("\n", " ")
        lines.append(f"slots: object={obj} | action={act}")
    lines.append("open_loops:")
    for i, loop in enumerate(open_loops, 1):
        topic = loop.topic.strip().replace("\n", " ")
        departure = loop.departure_utterance.strip().replace("\n", " ")
        label = (loop.activity_label or departure or topic).strip().replace("\n", " ")
        gloss = (loop.frame_gloss or activity_gloss(loop.activity_frame) if loop.activity_frame else label)
        gloss = gloss.strip().replace("\n", " ")
        lines.append(
            f"  {i}. loop_id={loop.loop_id} | topic={topic} | "
            f"label={label} | gloss={gloss} | departure={departure}"
        )
    return "\n".join(lines) + "\n"


def parse_ol7_response(
    text: str,
    *,
    utterance: str,
    open_loops: list[OpenLoopCandidate],
) -> Ol7Classification | None:
    data = _extract_json_object(text)
    if not data:
        return None

    signal = str(data.get("signal") or "none").strip()
    if signal not in VALID_SIGNALS:
        signal = "none"

    reason = str(data.get("reason") or "").strip()
    summary_raw = data.get("completion_summary")
    completion_summary = str(summary_raw).strip() if summary_raw not in (None, "", "null") else None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    choice_index: int | None = None
    raw_choice = data.get("choice_index")
    if raw_choice is not None and raw_choice != "null":
        try:
            choice_index = int(raw_choice)
        except (TypeError, ValueError):
            choice_index = None

    ids: list[str] = []
    raw_ids = data.get("close_loop_ids")
    if isinstance(raw_ids, list):
        for item in raw_ids:
            lid = str(item).strip()
            if lid and lid not in ids:
                ids.append(lid)

    valid_ids = {loop.loop_id for loop in open_loops}
    ids = [lid for lid in ids if lid in valid_ids]

    if not ids and choice_index is not None and 1 <= choice_index <= len(open_loops):
        ids = [open_loops[choice_index - 1].loop_id]

    if signal == "none":
        ids = []
        completion_summary = None

    return Ol7Classification(
        utterance=utterance,
        signal=signal,
        close_loop_ids=tuple(ids),
        completion_summary=completion_summary,
        confidence=confidence,
        reason=reason,
        choice_index=choice_index,
        raw=text,
    )


def classify_return_signal(
    *,
    utterance: str,
    open_loops: list[OpenLoopCandidate],
    utterance_kind: str | None = None,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
    close_shape: str | None = None,
    min_confidence: float | None = None,
    apply_confidence_gate: bool = True,
) -> Ol7Classification | None:
    """Stateless 日本語検定型 classifier; None on LLM/parse failure.

    When ``apply_confidence_gate`` is True (POC default), sub-threshold hits are
    returned as signal=none — gateway wiring should set False when routing to
    pending_check instead of treating low confidence as terminal no-op.
    """
    if not open_loops:
        return None
    if min_confidence is None:
        min_confidence = ol7_min_confidence()

    raw = run_classifier_turn(
        system=OL7_SYSTEM,
        user=build_ol7_task(
            utterance=utterance,
            open_loops=open_loops,
            utterance_kind=utterance_kind,
            object_phrase=object_phrase,
            action_phrase=action_phrase,
            close_shape=close_shape,
        ),
        max_tokens=_ol7_max_tokens(),
        temperature=0.2,
        log_label="OL7 return_signal",
    )
    if not raw:
        return None

    parsed = parse_ol7_response(raw, utterance=utterance, open_loops=open_loops)
    if not parsed:
        logger.warning("OL7: failed to parse classifier JSON")
        return None

    if parsed.signal == "none" or not parsed.close_loop_ids:
        return parsed

    if apply_confidence_gate and parsed.confidence < min_confidence:
        logger.info(
            "OL7: confidence %.2f below threshold %.2f — treating as no close",
            parsed.confidence,
            min_confidence,
        )
        return Ol7Classification(
            utterance=parsed.utterance,
            signal="none",
            close_loop_ids=(),
            completion_summary=None,
            confidence=parsed.confidence,
            reason=f"below_threshold: {parsed.reason}".strip(),
            choice_index=None,
            raw=parsed.raw,
        )

    return parsed
