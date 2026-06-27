"""Tests for GW-S2 / OL-GATE parse and gateway merge."""

from __future__ import annotations

from presence_ui.gateway.ol_gate import (
    OlGateParsed,
    merge_ol_gate_gateway,
    parse_ol_gate_response,
    seed_completion_verbs,
    should_run_ol_gate,
)


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


def test_should_run_ol_gate_skips_recall() -> None:
    assert should_run_ol_gate("煎餅覚えてる？") is False
    assert should_run_ol_gate("明日、角煮を作る") is True
