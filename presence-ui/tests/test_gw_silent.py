"""Tests for GW-S1 silent internal turn parsing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract

from presence_ui.gateway import direct_actions
from presence_ui.gateway.aozora import ReadingState
from presence_ui.gateway.gw_silent import PauseReflectionParsed, parse_pause_response
from presence_ui.gateway.reading_prompts import build_pause_reflection_from_gw_s1


def _ctx(*, session_id: str | None = None) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-25T13:00:00+00:00",
        local_time="2026-06-25T22:05:00+09:00",
        timezone="Asia/Tokyo",
        session_id=session_id,
        agent_state={
            "ts": "2026-06-25T13:00:00+00:00",
            "desires": {"literary_wander": 1.0},
            "discomforts": {"literary_wander": 0.8},
            "dominant_desire": "literary_wander",
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet tick",
        compact_prompt_block="[boundary] quiet_hours_active",
    )


def test_parse_pause_response_valid() -> None:
    parsed = parse_pause_response(
        '{"hook":"下人の勇気","felt":"uneasy","next_move":"advance",'
        '"interest_tags":["羅生門"],"followup_query":"下人とは誰"}'
    )
    assert parsed == PauseReflectionParsed(
        hook="下人の勇気",
        felt="uneasy",
        next_move="advance",
        interest_tags=("羅生門",),
        followup_query="下人とは誰",
    )


def test_parse_pause_response_rejects_invalid_next_move() -> None:
    parsed = parse_pause_response(
        '{"hook":"x","felt":"flat","next_move":"skip_ahead"}'
    )
    assert parsed is not None
    assert parsed.next_move == "advance"


def test_parse_pause_response_rejects_missing_hook() -> None:
    assert parse_pause_response('{"felt":"flat","next_move":"advance"}') is None


def test_build_pause_reflection_from_gw_s1_includes_hook_and_move() -> None:
    body = build_pause_reflection_from_gw_s1(
        title="羅生門",
        author="芥川",
        passage="下人は、大きな嚔をして。",
        passage_index=1,
        total_passages=40,
        sections_this_session=2,
        hook="下人の勇気",
        felt="uneasy",
        next_move="reread_same",
        interest_tags=["下人"],
        followup_query="なぜ門の下",
    )
    assert "下人の勇気" in body
    assert "reread_same" in body
    assert "なぜ門の下" in body


def test_reflect_uses_gw_s1_when_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    state = ReadingState(
        phase="pause",
        last_passage={
            "title": "羅生門",
            "author": "芥川",
            "text": "下人は、大きな嚔をして。",
            "passage_index": 2,
            "total_passages": 40,
            "next_passage_index": 3,
        },
        sections_this_session=1,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.direct_actions.load_reading_state",
        lambda: state,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.direct_actions.complete_reading_pause",
        lambda **kwargs: state,
    )

    stores = MagicMock()
    ctx = _ctx(session_id="sess-1")
    plan = MagicMock()

    gw_json = (
        '{"hook":"下人の一瞬","felt":"curious","next_move":"advance",'
        '"followup_query":"江戸の下人"}'
    )
    with (
        patch(
            "presence_ui.gateway.direct_actions.gw_s1_enabled",
            return_value=True,
        ),
        patch(
            "presence_ui.gateway.direct_actions.run_silent_internal_turn",
            return_value=gw_json,
        ) as silent_mock,
        patch(
            "presence_ui.gateway.direct_actions.write_private_reflection_direct",
            return_value=direct_actions.DirectActionOutcome(
                ok=True,
                action="write_private_reflection",
                summary="saved",
            ),
        ),
    ):
        outcome = direct_actions.reflect_on_aozora_passage_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    silent_mock.assert_called_once()
    assert outcome.ok
    assert outcome.action == "reflect_on_aozora_passage"
    assert "下人の一瞬" in outcome.summary
    assert outcome.detail == "羅生門"
