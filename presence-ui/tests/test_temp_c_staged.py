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
    stage1_fallback_events,
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


def test_inherit_when_multihop_and_utterance_fallback() -> None:
    events = inherit_when_phrases(
        [
            StagedEvent(index=0, what="書類作成", until_phrase="15時まで"),
            StagedEvent(index=1, what="散歩", action_phrase="行く", depends_on=0),
            StagedEvent(index=2, what="買い物", action_phrase="する", depends_on=1),
        ],
        utterance_fallback_when="明日",
    )
    assert events[0].effective_when_phrase == "明日"
    assert events[1].effective_when_phrase == "明日"
    assert events[2].effective_when_phrase == "明日"


def test_temp_c4_child_event_gets_resolved_date_in_loop_topic() -> None:
    result = StagedClassifyResult(
        utterance="明日、お昼ご飯を12時ごろ食べた後、県に提出する書類を作るよ",
        stage1=OlGateParsed(
            utterance="明日、お昼ご飯を12時ごろ食べた後、県に提出する書類を作るよ",
            utterance_kind="future_commitment",
            temporal_phrase="明日",
            inferred_temporal_phrase=None,
            temporal_source="explicit",
            object_phrase=None,
            action_phrase=None,
            action_terms=(),
            completion_verbs=(),
            ineligibility_reason=None,
        ),
        commitment_strength="firm",
        events=(
            StagedEvent(
                index=0,
                what="お昼ご飯",
                when_phrase="明日",
                action_phrase="食べる",
            ),
            StagedEvent(
                index=1,
                what="県に提出する書類",
                after_phrase="お昼ご飯を12時ごろ食べた後",
                action_phrase="作る",
                depends_on=0,
            ),
        ),
    )
    decisions = staged_to_gateway_decisions(
        result, ts="2026-06-28T11:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert len(decisions) == 2
    doc = decisions[1]
    assert doc.create_open_loop is True
    assert doc.detail.get("resolved_date") == "2026-06-29"
    assert "2026年6月29日" in doc.loop_topic
    assert doc.detail.get("event", {}).get("effective_when_phrase") == "明日"


def test_staged_gateway_creates_loops_for_action_and_duration_events() -> None:
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
    assert decisions[0].create_open_loop is True
    assert "入浴介助" in decisions[0].loop_topic
    assert "15時" in decisions[0].loop_topic
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
        event=StagedEvent(
            index=0, what="書類作成", when_phrase="明日", until_phrase="15時くらいまで"
        ),
    ) is True
    assert should_create_loop_for_event(
        utterance_kind="future_commitment",
        event=StagedEvent(index=1, what="角煮", action_phrase="作る"),
    ) is True


def test_stage1_fallback_events_for_past_completion() -> None:
    stage1 = parse_stage1_response(
        '{"utterance_kind":"past_completion","object_phrase":"試合","action_phrase":"見終わった",'
        '"temporal_phrase":null,"inferred_temporal_phrase":"いま"}',
        fallback_utterance="試合、見終わった",
    )
    assert stage1 is not None
    events = stage1_fallback_events(stage1)
    assert len(events) == 1
    assert events[0].what == "試合"
    assert events[0].action_phrase == "見終わった"


def test_staged_past_completion_empty_stage2_uses_stage1_fallback() -> None:
    stage1 = OlGateParsed(
        utterance="試合、見終わった",
        utterance_kind="past_completion",
        temporal_phrase=None,
        inferred_temporal_phrase="いま",
        temporal_source="inferred",
        object_phrase="試合",
        action_phrase="見終わった",
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    result = StagedClassifyResult(
        utterance="試合、見終わった",
        stage1=stage1,
        commitment_strength="firm",
        events=stage1_fallback_events(stage1),
    )
    decisions = staged_to_gateway_decisions(
        result, ts="2026-06-30T08:56:00+09:00", timezone="Asia/Tokyo"
    )
    assert len(decisions) == 1
    assert decisions[0].try_ol5_close is True
    assert "見終わった" in decisions[0].completion_verbs
