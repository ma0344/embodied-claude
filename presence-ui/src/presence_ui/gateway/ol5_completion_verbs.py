"""OL5-c — classifier-generated completion_verbs at open-loop create (e4b)."""

from __future__ import annotations

import logging
import os
from dataclasses import replace

from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.gateway.ol_gate import OlGateGatewayDecision

logger = logging.getLogger(__name__)

MAX_COMPLETION_VERBS = 10

OL5_C_SYSTEM = """あなたは予定タスクの完了報告フレーズ生成器です。
まー（人間）が「やり終えた」と報告するときに自然な **過去形の短い動詞句** を JSON 1 件だけ出力してください。

**ルール**
1. タスク内容に合う完了表現のみ（推測で無関係な動詞を足さない）
2. 過去形・口語（作った / 提出した / 行ってきた / 終わった 等）
3. `completion_verbs` は **最大 10 語** · 重複なし
4. 未来形・「〜する」「〜しよう」禁止
5. 活動名そのもの（名詞のみ）は入れない

**例**
- loop: 県に提出する書類 · action: 作る → ["作った","できた","完成した","提出した","送った","出した"]
- loop: 散歩に行く · action: 行く → ["行ってきた","行った","散歩してきた","戻ってきた"]

JSON のみ。markdown フェンス不可。"""


def ol5_c_enabled() -> bool:
    flag = os.environ.get("PRESENCE_OL5_C_ENABLED", "1").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _ol5_c_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_OL5_C_MAX_TOKENS", "280"))


def merge_completion_verbs(*parts: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Union verb lists; preserve order; cap at MAX_COMPLETION_VERBS."""
    out: list[str] = []
    for part in parts:
        for raw in part:
            verb = str(raw).strip()
            if not verb or verb in out:
                continue
            out.append(verb)
            if len(out) >= MAX_COMPLETION_VERBS:
                return tuple(out)
    return tuple(out)


def build_ol5_c_task(
    *,
    loop_topic: str,
    object_phrase: str | None,
    action_phrase: str | None,
) -> str:
    obj = (object_phrase or "").strip() or "null"
    act = (action_phrase or "").strip() or "null"
    topic = loop_topic.strip().replace("\n", " ")
    return (
        f"[gateway_internal — not for まー]\n"
        f"task: ol5_completion_verbs\n"
        f"loop_topic: {topic}\n"
        f"object_phrase: {obj}\n"
        f"action_phrase: {act}\n"
    )


def parse_completion_verbs_response(text: str) -> tuple[str, ...]:
    data = _extract_json_object(text)
    if not data:
        return ()
    raw = data.get("completion_verbs")
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    for item in raw:
        verb = str(item).strip()
        if verb and verb not in out:
            out.append(verb)
        if len(out) >= MAX_COMPLETION_VERBS:
            break
    return tuple(out)


def generate_completion_verbs_llm(
    *,
    loop_topic: str,
    object_phrase: str | None,
    action_phrase: str | None,
) -> tuple[str, ...]:
    """Stateless e4b completion-verb expansion; empty tuple on failure."""
    if not loop_topic.strip():
        return ()
    raw = run_classifier_turn(
        system=OL5_C_SYSTEM,
        user=build_ol5_c_task(
            loop_topic=loop_topic,
            object_phrase=object_phrase,
            action_phrase=action_phrase,
        ),
        max_tokens=_ol5_c_max_tokens(),
        temperature=0.25,
        log_label="OL5-c completion_verbs",
    )
    if not raw:
        return ()
    parsed = parse_completion_verbs_response(raw)
    if not parsed:
        logger.warning("OL5-c: failed to parse completion_verbs JSON")
    return parsed


def enrich_decision_completion_verbs(decision: OlGateGatewayDecision) -> OlGateGatewayDecision:
    """Merge OL5-a seed with classifier verbs when creating an open loop."""
    if not decision.create_open_loop or not ol5_c_enabled():
        return decision
    detail = dict(decision.detail)
    object_phrase = detail.get("object_phrase")
    action_phrase = detail.get("action_phrase")
    if not isinstance(object_phrase, str):
        object_phrase = None
    if not isinstance(action_phrase, str):
        action_phrase = None
    llm_verbs = generate_completion_verbs_llm(
        loop_topic=decision.loop_topic,
        object_phrase=object_phrase,
        action_phrase=action_phrase,
    )
    merged = merge_completion_verbs(decision.completion_verbs, llm_verbs)
    if llm_verbs:
        detail["ol5_c"] = True
    detail["completion_verbs"] = list(merged)
    return replace(decision, completion_verbs=merged, detail=detail)
