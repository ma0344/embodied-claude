"""BIO-8c somatic compose/plan side effects."""

from __future__ import annotations

import pytest

from interaction_orchestrator_mcp.schemas import InteractionContext
from presence_ui.services import body_state as bs
from presence_ui.services.somatic_context import (
    apply_somatic_plan_side_effects,
    build_somatic_prompt_block,
    enrich_interaction_context,
    is_morning_digest_window,
)


def _minimal_ctx(**updates) -> InteractionContext:
    base = {
        "ts": "2026-06-18T08:30:00+09:00",
        "local_time": "2026-06-18T08:30:00+09:00",
        "timezone": "Asia/Tokyo",
        "compact_prompt_block": "base",
        "prompt_summary": "base",
        "boundary_hints": [],
        "agent_state": {"ts": "2026-06-18T08:30:00+09:00"},
        "response_contract": {},
    }
    base.update(updates)
    return InteractionContext.model_validate(base)


def test_build_somatic_prompt_block_pending_quiet() -> None:
    somatic = {
        "degraded_organs": [{"organ": "eyes", "organ_ja": "目", "status": "failed", "summary": "曇ってた"}],
        "pending_unreported": [{"summary": "目が曇ってた"}],
    }
    block = build_somatic_prompt_block(
        somatic=somatic,
        quiet_active=True,
        local_time="2026-06-18T02:00:00+09:00",
        timezone="Asia/Tokyo",
        channel="chat",
        user_text=None,
    )
    assert "[somatic_state]" in block
    assert "夜間" in block
    assert "まーに話さない" in block


def test_enrich_attaches_somatic_state(tmp_path, monkeypatch) -> None:
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(state, organ="eyes", summary="目が…", action="see")
    bs.save_body_state(state)

    ctx = enrich_interaction_context(_minimal_ctx(), channel="chat", user_text="見て")
    assert ctx.somatic_state is not None
    assert len(ctx.somatic_state.get("pending_unreported") or []) == 1
    assert "[somatic_state]" in ctx.compact_prompt_block


def test_apply_marks_reported_on_answer(tmp_path, monkeypatch) -> None:
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    report = bs.note_organ_affliction(state, organ="eyes", summary="目が…", action="see")
    bs.save_body_state(state)

    apply_somatic_plan_side_effects(
        primary_move="answer_directly",
        channel="chat",
        quiet_active=False,
        local_time="2026-06-18T10:00:00+09:00",
        timezone="Asia/Tokyo",
        user_text="おはよう",
    )
    state2 = bs.load_body_state()
    assert state2.pending_reports[0].reported_to_ma is True


def test_apply_marks_reflected_on_private_quiet(tmp_path, monkeypatch) -> None:
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(state, organ="eyes", summary="目が…", action="see")
    bs.save_body_state(state)

    apply_somatic_plan_side_effects(
        primary_move="write_private_reflection",
        channel="autonomous",
        quiet_active=True,
        local_time="2026-06-18T02:00:00+09:00",
        timezone="Asia/Tokyo",
        user_text=None,
    )
    state2 = bs.load_body_state()
    assert state2.pending_reports[0].reflected_at is not None


@pytest.mark.parametrize(
    ("local_time", "expected"),
    [
        ("2026-06-18T07:30:00+09:00", True),
        ("2026-06-18T11:00:00+09:00", False),
    ],
)
def test_morning_digest_window(local_time: str, expected: bool) -> None:
    assert (
        is_morning_digest_window(local_time=local_time, timezone="Asia/Tokyo") is expected
    )
