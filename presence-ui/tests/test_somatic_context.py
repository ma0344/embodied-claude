"""BIO-8c somatic compose/plan side effects."""

from __future__ import annotations

import pytest

from interaction_orchestrator_mcp.schemas import InteractionContext
from presence_ui.services import body_state as bs
from presence_ui.services.somatic_context import (
    apply_somatic_plan_side_effects,
    apply_somatic_summary_token,
    build_somatic_prompt_block,
    enrich_interaction_context,
    is_morning_digest_window,
    somatic_detail_inject_needed,
    somatic_summary_token,
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


def _all_ok_body(tmp_path, monkeypatch):
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    for organ in list(state.organs):
        bs.note_organ_probe(state, organ=organ, status="ok", summary="ok")
    bs.save_body_state(state)
    return state


def test_build_somatic_prompt_block_pending_quiet() -> None:
    somatic = {
        "degraded_organs": [
            {"organ": "eyes", "organ_ja": "目", "status": "failed", "summary": "曇ってた"}
        ],
        "pending_unreported": [{"summary": "目が曇ってた"}],
        "escalation": {"level": "watch", "reasons": ["one organ degraded"]},
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
    assert "器官はおおむね正常" not in block


def test_build_somatic_prompt_block_no_ok_filler() -> None:
    """T6: even if called with empty degraded, never emit おおむね正常."""
    somatic = {
        "degraded_organs": [],
        "pending_unreported": [{"summary": "さっき目が曇ってた"}],
        "escalation": {"level": "none", "reasons": []},
    }
    block = build_somatic_prompt_block(
        somatic=somatic,
        quiet_active=False,
        local_time="2026-06-18T11:00:00+09:00",
        timezone="Asia/Tokyo",
        channel="chat",
        user_text="おはよう",
    )
    assert "[pending_body_reports" in block
    assert "器官はおおむね正常" not in block


def test_somatic_summary_token_helpers() -> None:
    assert (
        somatic_summary_token(
            {
                "degraded_organs": [],
                "pending_unreported": [],
                "escalation": {"level": "none"},
            }
        )
        == "somatic=ok"
    )
    assert (
        somatic_summary_token(
            {
                "degraded_organs": [{"organ": "eyes"}],
                "pending_unreported": [],
                "escalation": {"level": "watch"},
            }
        )
        == "somatic=watch"
    )
    assert (
        somatic_summary_token(
            {
                "degraded_organs": [],
                "pending_unreported": [{"summary": "x"}],
                "escalation": {"level": "none"},
            }
        )
        == "somatic=attention"
    )
    assert somatic_detail_inject_needed(
        {
            "degraded_organs": [],
            "pending_unreported": [{"summary": "x"}],
            "escalation": {"level": "none"},
        }
    )
    assert apply_somatic_summary_token("base somatic=ok", "somatic=watch") == (
        "base somatic=watch"
    )


def test_enrich_all_ok_no_detail_block(tmp_path, monkeypatch) -> None:
    """T1: healthy body → no [somatic_state], somatic=ok."""
    _all_ok_body(tmp_path, monkeypatch)
    ctx = enrich_interaction_context(
        _minimal_ctx(), channel="chat", user_text="おはよう"
    )
    assert "[somatic_state]" not in ctx.compact_prompt_block
    assert "器官はおおむね正常" not in ctx.compact_prompt_block
    assert "somatic=ok" in ctx.prompt_summary
    assert "somatic=ok" in ctx.compact_prompt_block
    assert ctx.somatic_state is not None


def test_enrich_eyes_failed_detail(tmp_path, monkeypatch) -> None:
    """T2: eyes failed → detail block, no ok filler, somatic=watch."""
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(state, organ="eyes", summary="目が曇ってた", action="see")
    bs.save_body_state(state)

    ctx = enrich_interaction_context(_minimal_ctx(), channel="chat", user_text="見て")
    assert "[somatic_state]" in ctx.compact_prompt_block
    assert "failed" in ctx.compact_prompt_block
    assert "器官はおおむね正常" not in ctx.compact_prompt_block
    assert "somatic=ok" not in ctx.prompt_summary
    assert "somatic=watch" in ctx.prompt_summary
    assert ctx.somatic_state is not None
    assert len(ctx.somatic_state.get("degraded_organs") or []) == 1


def test_enrich_elevated_escalation_section(tmp_path, monkeypatch) -> None:
    """T3: elevated → escalation section; health_safety still elevated/critical only."""
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(state, organ="eyes", summary="目NG", action="see")
    bs.note_organ_affliction(state, organ="voice", summary="声NG", action="speak")
    bs.save_body_state(state)

    ctx = enrich_interaction_context(_minimal_ctx(), channel="chat", user_text="調子")
    esc = (ctx.somatic_state or {}).get("escalation") or {}
    level = str(esc.get("level") or "none")
    assert level in {"elevated", "critical"}
    assert f"[somatic_escalation: {level}]" in ctx.compact_prompt_block
    assert f"somatic={level}" in ctx.prompt_summary
    # health_safety_active gate unchanged: elevated/critical only (not watch)
    assert level in {"elevated", "critical"}


def test_enrich_pending_only_attention(tmp_path, monkeypatch) -> None:
    """T4: organs ok but pending remains → detail + not somatic=ok."""
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(state, organ="eyes", summary="目が曇ってた", action="see")
    bs.note_organ_probe(state, organ="eyes", status="ok", summary="直った")
    bs.save_body_state(state)

    somatic = bs.somatic_state_dict(bs.load_body_state())
    assert not (somatic.get("degraded_organs") or [])
    assert len(somatic.get("pending_unreported") or []) == 1
    assert str((somatic.get("escalation") or {}).get("level") or "none") == "none"

    ctx = enrich_interaction_context(_minimal_ctx(), channel="chat", user_text="こんにちは")
    assert "[somatic_state]" in ctx.compact_prompt_block
    assert "[pending_body_reports" in ctx.compact_prompt_block
    assert "somatic=ok" not in ctx.prompt_summary
    assert "somatic=attention" in ctx.prompt_summary


def test_enrich_inquiry_same_as_healthy(tmp_path, monkeypatch) -> None:
    """T5: body-ok inquiry does not thicken inject (same as T1)."""
    _all_ok_body(tmp_path, monkeypatch)
    ctx = enrich_interaction_context(
        _minimal_ctx(), channel="chat", user_text="体大丈夫？調子どう？"
    )
    assert "[somatic_state]" not in ctx.compact_prompt_block
    assert "somatic=ok" in ctx.prompt_summary


def test_enrich_attaches_somatic_state(tmp_path, monkeypatch) -> None:
    """T7 regression: attach + detail when degraded."""
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
    bs.note_organ_affliction(state, organ="eyes", summary="目が…", action="see")
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
    """T8 quiet side-effect regression."""
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
    """T8 morning window regression."""
    assert (
        is_morning_digest_window(local_time=local_time, timezone="Asia/Tokyo") is expected
    )
