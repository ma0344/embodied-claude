"""Tests for SHIFT-R2 correction routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from presence_ui.gateway.correction_routing import (
    CorrectionParsed,
    parse_correction_stage2_response,
    route_correction,
    should_run_correction_stage2,
)
from presence_ui.heartbeat.interpretation_shift import (
    infer_interpretation_shifts,
    legacy_shift_hook_enabled,
)


def test_parse_correction_world_fact() -> None:
    parsed = parse_correction_stage2_response(
        '{"utterance":"違うみたい。松本市のHPに無いかな？",'
        '"correction_target":"world_fact",'
        '"persists_across_turns":false,'
        '"canonical_topic":"Matsumoto city website fact check",'
        '"old_interpretation":"Info is on city website",'
        '"new_interpretation":"May not be on city website",'
        '"confidence":0.88}',
        fallback_utterance="違うみたい。松本市のHPに無いかな？",
    )
    assert parsed is not None
    assert parsed.correction_target == "world_fact"
    assert parsed.persists_across_turns is False


def test_should_run_correction_stage2_only_for_correction_kind() -> None:
    assert should_run_correction_stage2(utterance_kind="correction") is True
    assert should_run_correction_stage2(utterance_kind="greeting") is False
    assert should_run_correction_stage2(utterance_kind="future_commitment") is False


def test_route_world_fact_writes_experience_not_shift() -> None:
    stores = MagicMock()
    parsed = CorrectionParsed(
        utterance="違うみたい。松本市のHPに無いかな？",
        correction_target="world_fact",
        persists_across_turns=False,
        canonical_topic="Matsumoto city website",
        old_interpretation="Listed on website",
        new_interpretation="Not on website",
        confidence=0.85,
    )
    outcome = route_correction(
        stores,
        person_id="ma",
        text=parsed.utterance,
        ts="2026-06-28T02:00:00+00:00",
        source_event_id="evt_test",
        parsed=parsed,
    )
    assert outcome.wrote_experience is True
    assert outcome.wrote_shift is False
    stores.orchestrator.record_interpretation_shift.assert_not_called()
    stores.orchestrator.record_agent_experience.assert_called_once()


def test_route_boundary_writes_boundary_and_shift() -> None:
    stores = MagicMock()
    stores.orchestrator.record_interpretation_shift.return_value = MagicMock(
        experience_id="shft_test"
    )
    stores.relationship.record_boundary.return_value = {"boundary_id": "boundary_test"}
    parsed = CorrectionParsed(
        utterance="夜は静かにして",
        correction_target="boundary",
        persists_across_turns=True,
        canonical_topic="quiet hours and presence",
        old_interpretation="May nudge at night",
        new_interpretation="Do not speak at night unless asked",
        confidence=0.9,
    )
    outcome = route_correction(
        stores,
        person_id="ma",
        text=parsed.utterance,
        ts="2026-06-28T02:00:00+00:00",
        source_event_id="evt_test",
        parsed=parsed,
    )
    assert outcome.wrote_boundary is True
    assert outcome.wrote_shift is True
    stores.relationship.record_boundary.assert_called_once()
    stores.orchestrator.record_interpretation_shift.assert_called_once()
    shift_payload = stores.orchestrator.record_interpretation_shift.call_args[0][0]
    assert shift_payload.topic == "quiet hours and presence"


def test_route_dismiss_closes_loops() -> None:
    stores = MagicMock()
    dismiss = MagicMock(closed_loops=["松本市HP"], cancelled_commitments=[])
    stores.relationship.dismiss_from_utterance.return_value = dismiss
    parsed = CorrectionParsed(
        utterance="松本市HPの話は忘れていい",
        correction_target="dismiss_topic",
        persists_across_turns=False,
        canonical_topic="Matsumoto HP thread",
        old_interpretation="Thread open",
        new_interpretation="Dismiss thread",
        confidence=0.86,
        dismiss_topic_hint="松本",
    )
    outcome = route_correction(
        stores,
        person_id="ma",
        text=parsed.utterance,
        ts="2026-06-28T02:00:00+00:00",
        source_event_id="evt_test",
        parsed=parsed,
    )
    assert outcome.closed_loops == ("松本市HP",)
    stores.orchestrator.record_interpretation_shift.assert_not_called()


def test_promote_correction_kind_from_other(monkeypatch) -> None:
    from presence_ui.gateway.correction_routing import promote_correction_kind_if_cued
    from presence_ui.gateway.ol_gate import OlGateParsed

    monkeypatch.setenv("PRESENCE_GW_CORRECTION_ROUTING", "1")
    stage1 = OlGateParsed(
        utterance="違うみたい。松本市のHPに無いかな？",
        utterance_kind="other",
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )
    promoted = promote_correction_kind_if_cued(stage1, utterance=stage1.utterance)
    assert promoted.utterance_kind == "correction"


def test_legacy_shift_hook_disabled_when_correction_routing_on(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_GW_CORRECTION_ROUTING", "1")
    assert legacy_shift_hook_enabled() is False
    shifts = infer_interpretation_shifts(
        person_id="ma",
        user_text="それは違う。松本市のHPに無い",
        reply_text="了解",
        ctx=None,
        plan=None,
    )
    assert shifts == []
