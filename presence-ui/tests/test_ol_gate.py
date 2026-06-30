"""Tests for GW-S2 / OL-GATE parse and gateway merge."""

from __future__ import annotations

from presence_ui.gateway.ol_gate import (
    OlGateParsed,
    merge_ol_gate_gateway,
    parse_ol_gate_response,
    promote_future_departure_if_cued,
    seed_completion_verbs,
    should_run_ol_gate,
)


def test_parse_ol_gate_past_completion_close_shape_explicit() -> None:
    parsed = parse_ol_gate_response(
        '{"utterance":"終わったよ","utterance_kind":"past_completion",'
        '"temporal_phrase":null,"inferred_temporal_phrase":"いま",'
        '"temporal_source":"inferred","object_phrase":null,"action_phrase":"終わった",'
        '"action_terms":[],"completion_verbs":[],"close_shape":"action_only",'
        '"ineligibility_reason":null}',
        fallback_utterance="終わったよ",
    )
    assert parsed is not None
    assert parsed.close_shape == "action_only"


def test_parse_ol_gate_infers_close_shape_from_slots() -> None:
    parsed = parse_ol_gate_response(
        '{"utterance":"お昼寝 終わった","utterance_kind":"past_completion",'
        '"object_phrase":"お昼寝","action_phrase":"終わった",'
        '"action_terms":[],"completion_verbs":[],"close_shape":null,'
        '"ineligibility_reason":null}',
        fallback_utterance="お昼寝 終わった",
    )
    assert parsed is not None
    assert parsed.close_shape == "activity_named"


def test_merge_past_completion_detail_includes_close_shape() -> None:
    parsed = OlGateParsed(
        utterance="終わったよ",
        utterance_kind="past_completion",
        temporal_phrase=None,
        inferred_temporal_phrase="いま",
        temporal_source="inferred",
        object_phrase=None,
        action_phrase="終わった",
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
        close_shape="action_only",
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-30T13:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.detail.get("close_shape") == "action_only"


def test_parse_ol_gate_future_commitment() -> None:
    parsed = parse_ol_gate_response(
        '{"utterance":"明日、角煮を作る","utterance_kind":"future_commitment",'
        '"temporal_phrase":"明日","inferred_temporal_phrase":null,'
        '"temporal_source":"explicit","object_phrase":"角煮を","action_phrase":"作る",'
        '"action_terms":["角煮"],"completion_verbs":[],"ineligibility_reason":null}',
        fallback_utterance="明日、角煮を作る",
    )
    assert parsed is not None
    assert parsed.utterance_kind == "future_commitment"
    assert parsed.action_terms == ("角煮",)


def test_parse_ol_gate_other() -> None:
    parsed = parse_ol_gate_response(
        '{"utterance":"また明日！","utterance_kind":"other",'
        '"temporal_phrase":"明日","object_phrase":null,"action_phrase":null,'
        '"action_terms":[],"completion_verbs":[],'
        '"ineligibility_reason":"挨拶"}',
    )
    assert parsed is not None
    assert parsed.utterance_kind == "other"


def test_merge_other_does_not_create_loop() -> None:
    parsed = OlGateParsed(
        utterance="また明日！",
        utterance_kind="other",
        temporal_phrase="明日",
        inferred_temporal_phrase=None,
        temporal_source="explicit",
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason="挨拶",
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-25T12:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is False
    assert decision.try_ol5_close is False


def test_merge_future_commitment_creates_loop() -> None:
    parsed = OlGateParsed(
        utterance="明日、角煮を作る",
        utterance_kind="future_commitment",
        temporal_phrase="明日",
        inferred_temporal_phrase=None,
        temporal_source="explicit",
        object_phrase="角煮を",
        action_phrase="作る",
        action_terms=("角煮",),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-25T12:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is True
    assert "角煮" in decision.loop_topic or "2026" in decision.loop_topic
    assert decision.action_terms == ("角煮",)
    assert decision.detail.get("stale_policy") == "default"


def test_merge_future_commitment_without_date_gets_until_completed() -> None:
    parsed = OlGateParsed(
        utterance="県に提出する書類を作る",
        utterance_kind="future_commitment",
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase="書類を",
        action_phrase="作る",
        action_terms=("書類",),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-29T10:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is True
    assert decision.detail.get("stale_policy") == "until_completed"


def test_seed_completion_verbs_for_作る() -> None:
    verbs = seed_completion_verbs("作る")
    assert "作った" in verbs
    assert "できた" in verbs


def test_merge_future_commitment_seeds_completion_verbs() -> None:
    parsed = OlGateParsed(
        utterance="明日、肉じゃがを作る",
        utterance_kind="future_commitment",
        temporal_phrase="明日",
        inferred_temporal_phrase=None,
        temporal_source="explicit",
        object_phrase="肉じゃがを",
        action_phrase="作る",
        action_terms=("肉じゃが",),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-25T12:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is True
    assert "作った" in decision.completion_verbs


def test_merge_past_completion_triggers_ol5() -> None:
    parsed = OlGateParsed(
        utterance="角煮、作った",
        utterance_kind="past_completion",
        temporal_phrase=None,
        inferred_temporal_phrase="いま",
        temporal_source="inferred",
        object_phrase="角煮",
        action_phrase="作った",
        action_terms=("角煮",),
        completion_verbs=("作った",),
        ineligibility_reason=None,
    )
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-25T12:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.try_ol5_close is True
    assert decision.create_open_loop is False


def test_merge_past_completion_seeds_verbs_from_action_phrase() -> None:
    """Stage1 JSON often omits completion_verbs — gateway must still close."""
    parsed = OlGateParsed(
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
    decision = merge_ol_gate_gateway(
        parsed, ts="2026-06-30T08:56:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.try_ol5_close is True
    assert "見終わった" in decision.completion_verbs
    assert "終わった" in decision.completion_verbs


def test_should_run_ol_gate_skips_recall() -> None:
    assert should_run_ol_gate("煎餅覚えてる？") is False
    assert should_run_ol_gate("明日、角煮を作る") is True


def test_promote_future_departure_from_past_completion() -> None:
    stage1 = OlGateParsed(
        utterance="これから、散歩に行ってくる",
        utterance_kind="past_completion",
        temporal_phrase="これから",
        inferred_temporal_phrase=None,
        temporal_source="explicit",
        object_phrase="散歩",
        action_phrase="行ってくる",
        action_terms=("散歩",),
        completion_verbs=("行ってくる",),
        ineligibility_reason=None,
    )
    promoted = promote_future_departure_if_cued(stage1, utterance=stage1.utterance)
    assert promoted.utterance_kind == "future_commitment"
    decision = merge_ol_gate_gateway(
        promoted, ts="2026-06-30T10:00:00+09:00", timezone="Asia/Tokyo"
    )
    assert decision.create_open_loop is True
    assert "散歩" in decision.loop_topic
