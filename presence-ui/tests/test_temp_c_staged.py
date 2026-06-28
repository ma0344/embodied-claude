"""Tests for TEMP-C3 staged classification."""

from __future__ import annotations

from presence_ui.gateway.ol_gate import OlGateParsed, merge_ol_gate_gateway
from presence_ui.gateway.temp_c_staged import (
    StagedClassifyResult,
    StagedEvent,
    inherit_when_phrases,
    parse_stage1_response,
    parse_stage2_response,
    should_create_loop_for_event,
    should_run_stage2,
    staged_to_gateway_decisions,
)


def test_parse_stage1_greeting() -> None:
    parsed = parse_stage1_response(
        '{"utterance":"おはよ","utterance_kind":"greeting",'
        '"temporal_phrase":null,"inferred_temporal_phrase":null,'
        '"temporal_source":null,"object_phrase":null,"action_phrase":null,'
        '"action_terms":[],"completion_verbs":[],"ineligibility_reason":null}',
        fallback_utterance="おはよ",
    )
    assert parsed is not None
    assert parsed.utterance_kind == "greeting"
    assert should_run_stage2(parsed) is False


def test_parse_stage2_bath_kakuni() -> None:
    strength, events = parse_stage2_response(
        # ruff: noqa: E501
        '{"utterance":"今日は入浴介助で15時位までかかりそうだから、帰ってきたらすぐ豚バラ軟骨角煮を作る感じだね。",'
        '"utterance_kind":"future_commitment","commitment_strength":"tentative",'
        '"events":[{"index":0,"what":"入浴介助","when_phrase":"今日","until_phrase":"15時位まで",'
        '"certainty":"estimate"},{"index":1,"what":"豚バラ軟骨角煮","after_phrase":"帰ってきたら",'
        '"lag_phrase":"すぐ","action_phrase":"作る","depends_on":0}]}',
        fallback_utterance="今日は入浴介助…",
        utterance_kind="future_commitment",
    )
    assert strength == "tentative"
    assert len(events) == 2
    assert events[1].effective_when_phrase == "今日"


def test_inherit_when_from_depends_on() -> None:
    events = inherit_when_phrases(
        [
            StagedEvent(index=0, what="入浴介助", when_phrase="今日"),
            StagedEvent(index=1, what="角煮", action_phrase="作る", depends_on=0),
        ]
    )
    assert events[1].effective_when_phrase == "今日"


def test_staged_gateway_creates_loop_only_for_action_event() -> None:
    result = StagedClassifyResult(
        utterance="今日は入浴介助…角煮…",
        stage1=OlGateParsed(
            utterance="今日は入浴介助…角煮…",
            utterance_kind="future_commitment",
            temporal_phrase="今日",
            inferred_temporal_phrase=None,
            temporal_source="explicit",
            object_phrase=None,
            action_phrase=None,
            action_terms=(),
            completion_verbs=(),
            ineligibility_reason=None,
        ),
        commitment_strength="tentative",
        events=(
            StagedEvent(index=0, what="入浴介助", when_phrase="今日", until_phrase="15時位まで"),
            StagedEvent(
                index=1,
                what="豚バラ軟骨角煮",
                after_phrase="帰ってきたら",
                action_phrase="作る",
                depends_on=0,
                effective_when_phrase="今日",
            ),
        ),
    )
    decisions = staged_to_gateway_decisions(
        result, ts="2026-06-27T10:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert len(decisions) == 2
    assert decisions[0].create_open_loop is False
    assert decisions[1].create_open_loop is True
    assert "角煮" in decisions[1].loop_topic or "豚バラ" in decisions[1].loop_topic


def test_greeting_merge_no_loop() -> None:
    parsed = OlGateParsed(
        utterance="おはよ",
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
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-28T08:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is False


def test_should_create_loop_for_event() -> None:
    assert should_create_loop_for_event(
        utterance_kind="future_commitment",
        event=StagedEvent(index=0, what="入浴介助", when_phrase="今日"),
    ) is False
    assert should_create_loop_for_event(
        utterance_kind="future_commitment",
        event=StagedEvent(index=1, what="角煮", action_phrase="作る"),
    ) is True
