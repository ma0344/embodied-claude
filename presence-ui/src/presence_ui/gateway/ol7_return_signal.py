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
from dataclasses import dataclass

from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object

logger = logging.getLogger(__name__)

VALID_SIGNALS = frozenset({"none", "explicit_completion", "return_signal"})

OL7_SYSTEM = """あなたは日本語の「用法選択」分類器です。
まー（人間）の短い発話が、**列挙された open loop（進行中タスク）のどれを完了した合図か**を判定し JSON 1 件だけを出力します。

## 比喩（日本語検定）
「欠陥」と同様、発話はリストの選択肢と**コロケーション（自然な語の組み合わせ）**でペアになるかで判定する。
- 最も自然な組み合わせが **1 つ** あればそれを選ぶ
- **どの選択肢とも不自然**なら close しない（正解なし）
- **リストにない行動**（例: お食事・昼食）を推測・捏造しない

## ルール
1. **選択肢は番号付き open_loops のみ**。リスト外のタスクを close しない
2. **原則 1 発話で 1 loop まで**。複数 close は同一発話に複数対象が明示された場合のみ
3. `signal`:
   - `explicit_completion`: 対象+完了語が同一発話に明確（例: 昼寝終わった、書類できた）
   - `return_signal`: 短い合図のみだが departure と強く対応（例: ただいま、ゆでた）
   - `none`: 挨拶・無関係・曖昧すぎる（例: おはよう、ごちそうさま）
4. `confidence` 0.0–1.0: コロケーションの自然さ。低いときは close しない想定
5. `completion_summary`: 完了報告の要約（表示用）。close しないときは null

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
    flag = os.environ.get("PRESENCE_OL7_ENABLED", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def ol7_min_confidence() -> float:
    try:
        return float(os.environ.get("PRESENCE_OL7_MIN_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _ol7_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_OL7_MAX_TOKENS", "320"))


def build_ol7_task(*, utterance: str, open_loops: list[OpenLoopCandidate]) -> str:
    u = utterance.strip().replace("\n", " ")
    lines = [
        "[gateway_internal — not for まー]",
        "task: ol7_return_signal",
        f"utterance: {u}",
        "open_loops:",
    ]
    for i, loop in enumerate(open_loops, 1):
        topic = loop.topic.strip().replace("\n", " ")
        departure = loop.departure_utterance.strip().replace("\n", " ")
        lines.append(f"  {i}. loop_id={loop.loop_id} | topic={topic} | departure={departure}")
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
        user=build_ol7_task(utterance=utterance, open_loops=open_loops),
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
