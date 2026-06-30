"""Stage1 contextual greeting (Q3a) — task context and gateway promote."""

from __future__ import annotations

from presence_ui.gateway.ol_gate import (
    OlGateParsed,
    promote_contextual_wake_greeting_if_cued,
)
from presence_ui.gateway.ol_gate_prompts import build_temp_c_stage1_task
from presence_ui.gateway.stage1_context import Stage1DepartureHint

_NAP_HINT = Stage1DepartureHint(
    loop_id="loop_nap",
    label="昼寝",
    gloss="昼寝",
    topic="もう一度 昼寝 してくる",
)


def test_build_stage1_task_includes_open_departure_loops() -> None:
    task = build_temp_c_stage1_task(
        utterance="おはよう",
        open_departure_loops=[_NAP_HINT],
    )
    assert "open_departure_loops:" in task
    assert "loop_id=loop_nap" in task
    assert "label=昼寝" in task


def test_build_stage1_task_none_when_no_departures() -> None:
    task = build_temp_c_stage1_task(utterance="おはよう")
    assert "open_departure_loops: (none)" in task


def test_promote_contextual_wake_greeting_single_departure() -> None:
    stage1 = OlGateParsed(
        utterance="おはよう",
        utterance_kind="greeting",
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    promoted = promote_contextual_wake_greeting_if_cued(
        stage1,
        utterance="おはよう",
        open_departure_loops=(_NAP_HINT,),
    )
    assert promoted.utterance_kind == "past_completion"
    assert promoted.close_shape == "action_only"
    assert promoted.action_phrase == "おはよう"


def test_promote_skips_without_departure_context() -> None:
    stage1 = OlGateParsed(
        utterance="おはよう",
        utterance_kind="greeting",
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    same = promote_contextual_wake_greeting_if_cued(
        stage1,
        utterance="おはよう",
        open_departure_loops=(),
    )
    assert same.utterance_kind == "greeting"


def test_promote_skips_multi_departure() -> None:
    stage1 = OlGateParsed(
        utterance="おはよう",
        utterance_kind="greeting",
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    walk = Stage1DepartureHint("loop_walk", "散歩", "散歩", "散歩 行ってくる")
    same = promote_contextual_wake_greeting_if_cued(
        stage1,
        utterance="おはよう",
        open_departure_loops=(_NAP_HINT, walk),
    )
    assert same.utterance_kind == "greeting"
